from optimum.exporters.onnx import main_export
from optimum.onnxruntime import ORTQuantizer
from optimum.onnxruntime.configuration import QuantizationConfig
from onnxruntime.quantization import QuantFormat, QuantizationMode

def quantize_reranker(model_name="BAAI/bge-reranker-base"):

    LOAD_DIR = "../../models/onnx_model"
    SAVE_DIR = "../../models/onnx_model_quant"

    main_export(
        model_name_or_path=model_name,
        output="onnx_model",
        task="text-classification"  # for reranker
    )

    quantizer = ORTQuantizer.from_pretrained(LOAD_DIR)

    quantization_config = QuantizationConfig(
        is_static=False,                      # dynamic quantization
        format=QuantFormat.QOperator,         # format of quantization
        mode=QuantizationMode.IntegerOps      # required for dynamic quantization
    )

    quantizer.quantize(
        save_dir=SAVE_DIR,
        quantization_config=quantization_config
    )

def main():
    quantize_reranker()

if __name__ == "__main__":
    main()