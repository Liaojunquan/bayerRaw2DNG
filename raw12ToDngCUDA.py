#项目来源于github的开源项目https://github.com/schoolpost/PyDNG   个人稍作修改
# image specs  Need to be modified depending on the picture 视图片情况需要修改
#本人使用华为P9相机进行测试，与其它相机可能存在数据出入，请以自己相机的为准
#相机元数据信息获取使用Android的camera2类库进行相机测试

#安装pucuda前请安装好CUDA Toolkit 9.0/9.1/9.2/10.0/10.1
#这个项目使用GPU进行加速计算，显卡不是NVIDIA的或无CUDA的请用CPU计算的项目:raw12ToDNG8or10or12or16.py

from timeit import default_timer as timer
from pydng.core import RAW2DNG, DNGTags, Tag
import numpy as np
import struct, collections
import threading
import pycuda.autoinit
import pycuda.driver as drv
from pycuda.compiler import SourceModule

global_time = timer()    #开始计时
width = 1920             #图片宽度
height = 1080            #图片高度
bpp= 12   #输出位深只有8、10、12、14和16这5种数值可选  Only 8, 10, 12, 14 and 16 are available

#低位深转高位深仅仅填充0在高位，无实际意义! 高位深转低位深，可以减少文件大小。
#Low depth to high depth only fill 0 in the high, no practical significance! High depth to low depth, can reduce the file size.
    
#用于测试像素最大最小亮度值
"""minNum = 1000000
maxNum = 0
for i in rawFlatImage:
    if i < minNum:
        minNum = i
    if i > maxNum:
        maxNum = i
print("min="+str(minNum)+"  max="+str(maxNum))"""
#rawImage = rawImage >> (16 - bpp)

# uncalibrated color matrix, just for demo.                3*3颜色矩阵[R,G,B]
#[x,y]其中，x表示分子，y表示分母，即x/y
"""ccm1 = [[19549, 10000], [-7877, 10000], [-2582, 10000],	
        [-5724, 10000], [10121, 10000], [1917, 10000],
        [-1267, 10000], [ -110, 10000], [ 6621, 10000]]

ccm2 = [[13244, 10000], [-5501, 10000], [-1248, 10000],
        [-1508, 10000], [9858, 10000], [1935, 10000],
        [-270, 10000], [-1083, 10000], [4366, 10000]]

fm1 = [[612, 1024], [233, 1024], [139, 1024],
        [199, 1024], [831, 1024], [-6, 1024],
        [15, 1024], [-224, 1024], [1049, 1024]]

fm2 = [[612, 1024], [233, 1024], [139, 1024],
        [199, 1024], [831, 1024], [-6, 1024],
        [15, 1024], [-224, 1024], [1049, 1024]]

nccm1 = [[10000, 10000], [0, 10000], [0, 10000],	
         [0, 10000], [10000, 10000], [0, 10000],
         [0, 10000], [ 0, 10000], [ 10000, 10000]]

nccm2 = [[10000, 10000], [0, 10000], [0, 10000],	
         [0, 10000], [10000, 10000], [0, 10000],
         [0, 10000], [ 0, 10000], [ 10000, 10000]]"""

#neutralColorPoint = [[273,355],[1,1],[91,256]]  #白炽灯
#自动    [[1092, 1951], [1, 1], [1092, 2129]]  自动的矩阵值根据场景不同发生变化
#荧光灯  [[1092, 2117], [1, 1], [1092, 2305]]
#暖荧光  [[1092, 2435], [1, 1], [91, 207]]
#日光    [[78, 163], [1, 1], [52, 89]]
#多云    [[546, 1367], [1, 1], [364, 509]]
#黄昏    [[546, 815], [1, 1], [182, 537]]
#阴天    [[182, 489], [1, 1], [7, 9]]

mod = SourceModule("""
__global__ void func12(unsigned short *r,unsigned char *i,size_t L)
{
    const int index = blockIdx.x * blockDim.x + threadIdx.x;
    if(index >= L)
    {
     return;
    }
    const int yushu = index % 2;
    const int shang = index / 2;
    if(yushu == 0)
    {
     r[index] = (i[index+shang] | (i[index+shang+1] & 0xF0) << 4);
    }
    else if(yushu == 1)
    {
     r[index] = ((i[index+shang] & 0x0F) | i[index+shang+1] << 4);
    }
    
}

__global__ void func10(unsigned short *r,unsigned char *i,size_t L)
{
    const int index = blockIdx.x * blockDim.x + threadIdx.x;
    if(index >= L)
    {
     return;
    }
    const int yushu = index % 2;
    const int shang = index / 2;
    if(yushu == 0)
    {
     r[index] = (i[index+shang] | (i[index+shang+1] & 0xF0) << 4) / 4;
    }
    else if(yushu == 1)
    {
     r[index] = ((i[index+shang] & 0x0F) | i[index+shang+1] << 4) / 4;
    }
}

__global__ void func8(unsigned short *r,unsigned char *i,size_t L)
{
    const int index = blockIdx.x * blockDim.x + threadIdx.x;
    if(index >= L)
    {
     return;
    }
    const int yushu = index % 2;
    const int shang = index / 2;
    if(yushu == 0)
    {
     r[index] = (i[index+shang] | (i[index+shang+1] & 0xF0) << 4) / 16;
    }
    else if(yushu == 1)
    {
     r[index] = ((i[index+shang] & 0x0F) | i[index+shang+1] << 4) / 16;
    }
}
""")    #CUDA函数
func = mod.get_function("func12")
if bpp == 10:
    func = mod.get_function("func10")
elif bpp == 8:
    func = mod.get_function("func8")
dev = drv.Device(0)
max_thread_pre_block = dev.get_attribute(drv.device_attribute.MAX_BLOCK_DIM_X)
        
def conver(fileID):
    numPixels = width * height
    blockSize = 1
    if float(numPixels//max_thread_pre_block) == (numPixels/max_thread_pre_block):
        blockSize = numPixels//max_thread_pre_block
    else:
        blockSize = numPixels//max_thread_pre_block + 1
    buffSize = int(1.5*numPixels)
    filePath = r'C:/Users/Administrator/Desktop/bayerRaw2DNG/extras/'      #10位raw文件所在文件夹
    rawFile = filePath + 'RAW_000' + str(fileID) + '.raw12'          #10位拜尔图像文件路径
    rf = open(rawFile, mode='rb')
    rawData = struct.unpack("B"*buffSize,rf.read(buffSize))    #struct.unpack("H"*numPixels,rf.read(2*numPixels))
    rawFlatImage = np.zeros(numPixels, dtype=np.uint16)     #像素数组  16位无符号整型
    npData = np.array(rawData, dtype=np.uint8)
    L = np.int32(numPixels)
    func(drv.InOut(rawFlatImage), drv.In(npData), L, block=(max_thread_pre_block,1,1), grid=(blockSize,1))        #调用CUDA进行计算
    rawImage = np.reshape(rawFlatImage,(height,width))
        
    ccm1 = [[19549, 10000], [-7877, 10000], [-2582, 10000],	
        [-5724, 10000], [10121, 10000], [1917, 10000],
        [-1267, 10000], [ -110, 10000], [ 6621, 10000]]
    ccm2 = [[13244, 10000], [-5501, 10000], [-1248, 10000],
        [-1508, 10000], [9858, 10000], [1935, 10000],
        [-270, 10000], [-1083, 10000], [4366, 10000]]
    fm1 = [[612, 1024], [233, 1024], [139, 1024],
        [199, 1024], [831, 1024], [-6, 1024],
        [15, 1024], [-224, 1024], [1049, 1024]]
    fm2 = [[612, 1024], [233, 1024], [139, 1024],
        [199, 1024], [831, 1024], [-6, 1024],
        [15, 1024], [-224, 1024], [1049, 1024]]
        
    t = DNGTags()
    t.set(Tag.ImageWidth, width)            #图像宽度像素  Need to be modified depending on the picture 视图片情况需要修改
    t.set(Tag.ImageLength, height)          #图像高度像素  Need to be modified depending on the picture 视图片情况需要修改
    t.set(Tag.TileWidth, width)
    t.set(Tag.TileLength, height)
    t.set(Tag.Orientation, 1)               #旋转角度
    t.set(Tag.PhotometricInterpretation, 32803)     #光度解析  32803
    t.set(Tag.SamplesPerPixel, 1)
    t.set(Tag.BitsPerSample, bpp)                #每像素位深  Need to be modified depending on the picture 视图片情况需要修改
    t.set(Tag.CFARepeatPatternDim, [2,2])
    t.set(Tag.CFAPattern, [0, 1, 1, 2])          #0=红色 1=绿色 2=蓝色 拜尔矩阵RGGB排列  Need to be modified depending on the picture 视图片情况需要修改
    t.set(Tag.BlackLevel, 0)               #(1984 >> (16 - bpp))黑场
    t.set(Tag.WhiteLevel, (1 << bpp)-1)           #((1 << bpp) -1) 16bit 白场
    t.set(Tag.ColorMatrix1, ccm1)          #颜色矩阵1
    t.set(Tag.ColorMatrix2, ccm2)          #颜色矩阵2
    t.set(Tag.CalibrationIlluminant1, 21)           #校准光源 21
    t.set(Tag.CalibrationIlluminant2, 21)           #校准光源                               Need to be modified depending on the picture 视图片情况需要修改
    t.set(Tag.AsShotNeutral, [[1092, 1951], [1, 1], [1092, 2129]])   #白平衡白点R,G,B矩阵  Need to be modified depending on the picture 视图片情况需要修改  [[1000,1567],[1000,1000],[1000,2250]]
    t.set(Tag.BaselineExposure, [[1,1],[1,1]])      #曝光补偿                             Need to be modified depending on the picture 视图片情况需要修改
    t.set(Tag.DNGVersion, [1, 4, 0, 0])
    t.set(Tag.DNGBackwardVersion, [1, 2, 0, 0])
    t.set(Tag.Make, "Camera Brand")
    t.set(Tag.Model, "Camera Model")
    t.set(Tag.PreviewColorSpace, 2)
    t.set(Tag.Software, "PyDNG")
    t.set(Tag.ForwardMatrix1,fm1)
    t.set(Tag.ForwardMatrix1,fm2)

    print("Save File " + "DNG_000" + str(fileID) + ".dng")
    RAW2DNG().convert(rawImage, tags=t, filename=("DNG_000"+str(fileID)), path="")
        
#------------------------------------------------------------------------------------------------------------------------------------------------------------
startNum = 18     #起始编号
endNum = 18       #结束编号
for f in range(startNum,endNum+1):
    conver(f)
run_time = timer() - global_time
print("总运行时间 %f s" % run_time)
