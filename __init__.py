from .nodes import (
    API429EditImage,
    API429GenerateImage,
    API429ImageQueue,
    API429PriceQuote,
)

NODE_CLASS_MAPPINGS = {
    cls.__name__: cls
    for cls in (
        API429GenerateImage,
        API429EditImage,
        API429ImageQueue,
        API429PriceQuote,
    )
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "API429GenerateImage": "API429 · Generate Image",
    "API429EditImage": "API429 · Edit Reference Image",
    "API429ImageQueue": "API429 · Image Queue",
    "API429PriceQuote": "API429 · Current Image Prices",
}
