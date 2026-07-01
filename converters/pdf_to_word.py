from pdf2docx import Converter
import os


def convert_pdf_to_word(input_path: str, output_path: str) -> dict:
    cv = Converter(input_path)
    cv.convert(output_path, start=0, end=None)
    cv.close()
    return {"success": True, "output": output_path}
