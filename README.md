# bayerRaw2DNG
将传感器的原始数据bayerRaw文件转换为DNG文件，方便后期处理

项目来源https://github.com/schoolpost/PyDNG

根据自己手机华为P9摄像头的数据和照片的元数据，自己稍作修改，例如颜色矩阵值、图片长度和宽度、白平衡等等。

源raw文件可以是8位、10位、12位或16位的，它分别可以转为16位、12位、10位或8位的DNG文件。若是使用达芬奇调色，建议转成10位DNG。使用Adobe系列软件，可以转成16位或8位DNG文件。

为了加快转换速度，我添加了CUDA加速程序，在raw10ToDNGCUDA.py和raw12ToDNGCUDA.py项目上，比用CPU来处理的raw10ToDNG8or10or12or14or16.py和raw12ToDNG8or10or12or14or16.py项目快5倍！！！

raw8ToDNG8or10or12or14or16.py和raw16ToDNG8or10or12or14or16.py项目没有CUDA加速程序，是因为这两个项目无需复杂的位运算，使用CPU计算效果已经不错了。

要是用带CUDA加速的项目，你的NVIDIA显卡得支持CUDA，需要先安装NVIDIA的CUDA Toolkit 9.0或9.1或9.2或10.0等的CUDA库，然后再安装pycuda！我的配置是GTX 1050Ti，CUDA9.0，驱动是10.1的。

CUDA项目首次运行会自动编译cu程序，会比较慢，但第二次之后运行就不需要编译cu程序了，你会看见很快的计算然后保存DNG文件!