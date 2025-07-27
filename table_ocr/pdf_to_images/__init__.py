import os
import re
import subprocess

from table_ocr.util import get_logger, working_dir

logger = get_logger(__name__)

# Wrapper around the Poppler command line utility "pdfimages" and helpers for
# finding the output files of that command.
# adding an optional dir folder where temporary image and other files will get created. 
# It is responsibility of the caller to delete or keep such dir.
def pdf_to_images(pdf_filepath, output_dir=None):
    """
    Turn a pdf into images
    Returns the filenames of the created images sorted lexicographically.
    
    Args:
        pdf_filepath: Path to the PDF file
        output_dir: Optional directory to save images to. If None, uses the directory of the PDF.
    """

    if not os.path.isabs(pdf_filepath):
        pdf_filepath = os.path.abspath(pdf_filepath)

    directory, filename = os.path.split(pdf_filepath)
    # Use output_dir if provided, otherwise use the PDF's directory
    target_dir = output_dir if output_dir is not None else directory
    image_filenames = pdfimages(pdf_filepath, target_dir)

    # Since pdfimages creates a number of files named each for there page number
    # and doesn't return us the list that it created
    return sorted([os.path.join(target_dir, f) for f in image_filenames])


def pdfimages(pdf_filepath, output_dir=None):
    """
    Uses the `pdfimages` utility from Poppler
    (https://poppler.freedesktop.org/). Creates images out of each page. Images
    are prefixed by their name sans extension and suffixed by their page number.

    This should work up to pdfs with 999 pages since find matching files in dir
    uses 3 digits in its regex.
    
    Args:
        pdf_filepath: Path to the PDF file
        output_dir: Optional directory to save images to. If None, uses the directory of the PDF.
    """
    directory, filename = os.path.split(pdf_filepath)
    if output_dir is None:
        output_dir = directory
    if not os.path.isabs(output_dir):
        output_dir = os.path.abspath(output_dir)
    filename_sans_ext = filename.split(".pdf")[0]

    try:
        # pdfimages outputs results to the current working directory
        with working_dir(output_dir):
            result = subprocess.run(
                ["pdfimages", "-png", pdf_filepath, filename_sans_ext], 
                capture_output=True, 
                check=True
            )
            
        image_filenames = find_matching_files_in_dir(filename_sans_ext, output_dir)
        logger.debug(
            "Converted {} into files:\n{}".format(pdf_filepath, "\n".join(image_filenames))
        )
        return image_filenames
        
    except subprocess.CalledProcessError as e:
        error_message = f"Error running pdfimages on {pdf_filepath}: {e}"
        logger.error(error_message)
        if e.stderr:
            logger.error(f"pdfimages stderr: {e.stderr.decode('utf-8', errors='replace')}")
        raise RuntimeError(error_message) from e
        
    except FileNotFoundError as e:
        error_message = f"pdfimages command not found. Make sure Poppler is installed: {e}"
        logger.error(error_message)
        raise RuntimeError(error_message) from e
        
    except Exception as e:
        error_message = f"Unexpected error processing PDF {pdf_filepath}: {e}"
        logger.error(error_message)
        raise RuntimeError(error_message) from e


def find_matching_files_in_dir(file_prefix, directory):
    files = [
        filename
        for filename in os.listdir(directory)
        if re.match(r"{}-\d{{3}}.*\.png".format(re.escape(file_prefix)), filename)
    ]
    return files

def preprocess_img(filepath, tess_params=None):
    """Processing that involves running shell executables,
    like mogrify to rotate.

    Uses tesseract to detect rotation.

    Orientation and script detection is only available for legacy tesseract
    (--oem 0). Some versions of tesseract will segfault if you let it run OSD
    with the default oem (3).
    """
    if tess_params is None:
        tess_params = ["--psm", "0", "--oem", "0"]
    rotate = get_rotate(filepath, tess_params)
    logger.debug("Rotating {} by {}.".format(filepath, rotate))
    mogrify(filepath, rotate)


def get_rotate(image_filepath, tess_params):
    """
    """
    tess_command = ["tesseract"] + tess_params + [image_filepath, "-"]
    output = (
        subprocess.check_output(tess_command)
        .decode("utf-8")
        .split("\n")
    )
    output = next(l for l in output if "Rotate: " in l)
    output = output.split(": ")[1]
    return output


def mogrify(image_filepath, rotate):
    subprocess.run(["mogrify", "-rotate", rotate, image_filepath])
