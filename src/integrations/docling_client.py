from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from docling_core.types.doc.document import DoclingDocument


def _convert(pdf_path: Path, device: str) -> "DoclingDocument":
    from docling.document_converter import DocumentConverter
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import PdfFormatOption

    options = PdfPipelineOptions(
        accelerator_options=AcceleratorOptions(device=device)
    )
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
    return converter.convert(str(pdf_path)).document


def _is_app_control_cuda_error(error: Exception) -> bool:
    current: BaseException | None = error
    app_control_block = False
    cuda_library_block = False
    while current is not None:
        if getattr(current, "winerror", None) == 4551:
            app_control_block = True
        if "c10_cuda.dll" in str(current).lower():
            cuda_library_block = True
        current = current.__cause__ or current.__context__
    return app_control_block and cuda_library_block


def _gpu_status(device: str) -> str:
    import onnxruntime

    status = f"GPU ({device})"
    if "CUDAExecutionProvider" not in onnxruntime.get_available_providers():
        status += "; OCR CUDA sağlayıcısı yok"
    return status


def convert_pdf(
    pdf_path: Path, on_device_selected: Callable[[str], None] | None = None
) -> tuple["DoclingDocument", str]:
    from docling.datamodel.accelerator_options import AcceleratorDevice
    from docling.utils.accelerator_utils import decide_device

    try:
        device = decide_device(AcceleratorDevice.AUTO.value)
    except Exception as error:
        if not _is_app_control_cuda_error(error):
            raise
        if on_device_selected:
            on_device_selected("CUDA engellendi; CPU yedeklemesiyle Docling başlıyor")
        return _convert(pdf_path, AcceleratorDevice.CPU.value), (
            "CPU (Windows Uygulama Denetimi CUDA'yı engelledi)"
        )

    if not device.startswith("cuda"):
        if on_device_selected:
            on_device_selected("CPU seçildi; Docling başlıyor")
        return _convert(pdf_path, AcceleratorDevice.CPU.value), "CPU"

    if on_device_selected:
        on_device_selected(f"{_gpu_status(device)} seçildi; Docling başlıyor")
    try:
        return _convert(pdf_path, device), _gpu_status(device)
    except Exception as error:
        if not _is_app_control_cuda_error(error):
            raise

    if on_device_selected:
        on_device_selected(
            "CUDA Windows Uygulama Denetimi tarafından engellendi; "
            "CPU yedeklemesi başlıyor"
        )
    return _convert(pdf_path, AcceleratorDevice.CPU.value), (
        "CPU yedeklemesi (Windows Uygulama Denetimi CUDA'yı engelledi)"
    )
