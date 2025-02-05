import aspose.cad as cad
from aspose.cad import Color
from aspose.cad.imageoptions import StpOptions

image = cad.Image.load("BAT1_SETA_HOUSE1.fbx")

cadRasterizationOptions = cad.imageoptions.CadRasterizationOptions()
cadRasterizationOptions.page_height = 800.5
cadRasterizationOptions.page_width = 800.5
cadRasterizationOptions.zoom = 1.5
cadRasterizationOptions.layers = "Layer"
cadRasterizationOptions.background_color = Color.green

options = StpOptions()
options.vector_rasterization_options = cadRasterizationOptions

image.save("result.stp", options)