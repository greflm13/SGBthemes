import os
import re
import sys
import json
import gzip
import shutil
import base64
import logging
import colorsys
import fileinput
import urllib.parse
import urllib.request
from typing import List
from datetime import datetime
from selenium import webdriver
from pythonjsonlogger import jsonlogger
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

if __package__ is None:
    PACKAGE = ""
else:
    PACKAGE = __package__
SCRIPTDIR = os.path.dirname(os.path.realpath(__file__).removesuffix(PACKAGE))
LOG_DIR = os.path.join(SCRIPTDIR, "logs")
LATEST_LOG_FILE = os.path.join(LOG_DIR, "latest.jsonl")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


def log_format(keys):
    """
    Generates a list of format strings based on the given keys.

    Args:
        keys (list): A list of string keys that represent the log attributes (e.g., 'asctime', 'levelname').

    Returns:
        list: A list of formatted strings for each key, in the format "%(key)s".
    """
    return [f"%({i})s" for i in keys]


def rotate_log_file(compress=False):
    """
    Truncates the 'latest.jsonl' file after optionally compressing its contents to a timestamped file.
    The 'latest.jsonl' file is not deleted or moved, just emptied.

    Args:
        compress (bool): If True, compress the old log file using gzip.
    """
    if os.path.exists(LATEST_LOG_FILE):
        with open(LATEST_LOG_FILE, "r+", encoding="utf-8") as f:
            first_line = f.readline()
            try:
                first_log = json.loads(first_line)
                first_timestamp = first_log.get("asctime")
                first_timestamp = first_timestamp.split(",")[0]
            except (json.JSONDecodeError, KeyError):
                first_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            safe_timestamp = first_timestamp.replace(":", "-").replace(" ", "_")
            old_log_filename = os.path.join(LOG_DIR, f"{safe_timestamp}.jsonl")

            # Write contents to the new file
            with open(old_log_filename, "w", encoding="utf-8") as old_log_file:
                f.seek(0)  # Go back to the beginning of the file
                shutil.copyfileobj(f, old_log_file)

            if compress:
                with open(old_log_filename, "rb") as f_in:
                    with gzip.open(f"{old_log_filename}.gz", "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(old_log_filename)

            # Truncate the original file
            f.seek(0)
            f.truncate()


def setup_logger(level=logging.INFO):
    """
    Configures the logging system with a custom format and outputs logs in JSON format.

    The logger will write to the 'logs/latest.jsonl' file, and it will include
    multiple attributes such as the time of logging, the filename, function name, log level, etc.

    Returns:
        logging.Logger: A configured logger instance that can be used to log messages.
    """
    _logger = logging.getLogger(name="defaultlogger")

    supported_keys = [
        "asctime",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "process",
        "processName",
        "relativeCreated",
        "thread",
        "threadName",
    ]

    custom_format = " ".join(log_format(supported_keys))
    formatter = jsonlogger.JsonFormatter(custom_format)

    log_handler = logging.FileHandler(LATEST_LOG_FILE)
    log_handler.setFormatter(formatter)

    _logger.addHandler(log_handler)
    _logger.setLevel(level=level)

    return _logger


def setup_consolelogger(level=logging.INFO):
    """
    Configures the logging system to output logs in console and JSON format.

    The logger will write to the 'logs/latest.jsonl' file, and it will include
    multiple attributes such as the time of logging, the filename, function name, log level, etc.

    Returns:
        logging.Logger: A configured logger instance that can be used to log messages.
    """
    _logger = logging.getLogger(name="consolelogger")

    supported_keys = [
        "asctime",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "process",
        "processName",
        "relativeCreated",
        "thread",
        "threadName",
    ]

    custom_format = " ".join(log_format(supported_keys))
    formatter = jsonlogger.JsonFormatter(custom_format)

    log_handler = logging.FileHandler(LATEST_LOG_FILE)
    log_handler.setFormatter(formatter)

    _logger.addHandler(log_handler)
    _logger.addHandler(logging.StreamHandler())
    _logger.setLevel(level=level)
    return _logger


rotate_log_file(compress=True)
logger = setup_logger()


def extract_colorscheme(theme_path: str) -> dict[str, str]:
    """
    Extract color scheme from a CSS theme file.

    Parameters:
    -----------
    theme_path : str
        Path to the CSS theme file.

    Returns:
    --------
    dict[str, str]
        dictionary containing color scheme variables and their hexadecimal values.
    """
    logger.info("extracting color scheme from theme file", extra={"theme_path": theme_path})
    pattern = r"--(color[1-4]|bcolor1):\s*(#[0-9a-fA-F]+|rgba?\([^)]*\)|hsla?\([^)]*\)|[a-zA-Z]+);"
    colorscheme = {}

    with open(theme_path, "r", encoding="utf-8") as f:
        filecontent = f.read()

    matches = re.findall(pattern, filecontent)

    for match in matches:
        variable_name = match[0]
        color_value = match[1]
        hex_color_value = css_color_to_hex(color_value)
        colorscheme[variable_name] = hex_color_value
        logger.debug("extracted variable", extra={"variable": variable_name, "value": hex_color_value})

    return colorscheme


def css_color_to_hex(css_color: str) -> str:
    """
    Converts a CSS color string to its hexadecimal representation.

    Args:
        css_color (str): The CSS color string to convert.

    Returns:
        str: The hexadecimal representation of the CSS color.

    Raises:
        ValueError: If the input CSS color string is invalid or unrecognized.

    Example:
        >>> css_color_to_hex('#ff0000')
        '#ff0000'
        >>> css_color_to_hex('rgb(255, 0, 0)')
        '#ff0000'
        >>> css_color_to_hex('hsl(0, 100%, 50%)')
        '#ff0000'
        >>> css_color_to_hex('blue')
        '#0000ff'
    """

    # Helper function to convert RGB tuple to hexadecimal string
    def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
        logger.debug("converting rgb tuple to hex string", extra={"rgb": rgb})
        return "#{:02x}{:02x}{:02x}".format(*rgb)

    # Helper function to convert HSL tuple to RGB tuple
    def hsl_to_rgb(hsl: tuple[int, float, float]) -> tuple[int, int, int]:
        logger.debug("converting hsl tuple to rgb tuple", extra={"hsl": hsl})
        r, g, b = colorsys.hls_to_rgb(hsl[0] / 360, hsl[1] / 100, hsl[2] / 100)
        return (round(r * 255), round(g * 255), round(b * 255))

    # Regular expression pattern to match CSS colors
    color_pattern = re.compile(
        r"^(?:(?P<hex>#(?:[0-9a-fA-F]{3}){1,2})|"  # Hexadecimal colors
        r"(?P<rgb>rgba?\((?P<r>\d+%?),\s*(?P<g>\d+%?),\s*(?P<b>\d+%?)(?:,\s*(?P<a>\d*\.?\d+)?)?\))|"  # RGB(a) colors
        r"(?P<hsl>hsla?\((?P<h>\d+),\s*(?P<s>\d+)%,\s*(?P<l>\d+)%(?:,\s*(?P<alpha>\d*\.?\d+)?)?\))|"  # HSL(a) colors
        r"(?P<name>[a-zA-Z]+))$"  # Named colors
    )

    match = color_pattern.match(css_color.strip())

    if not match:
        logger.error("invalid CSS color format", extra={"css_color": css_color})
        raise ValueError("Invalid CSS color format")

    groups = match.groupdict()

    if groups["hex"]:
        hex_color = groups["hex"]
        if len(hex_color) == 4:  # Convert short hex to full hex
            hex_color = "".join([c * 2 for c in hex_color[1:]])
        return hex_color.lower()

    elif groups["rgb"]:
        r = int(groups["r"].rstrip("%")) * 255 // 100 if "%" in groups["r"] else int(groups["r"])
        g = int(groups["g"].rstrip("%")) * 255 // 100 if "%" in groups["g"] else int(groups["g"])
        b = int(groups["b"].rstrip("%")) * 255 // 100 if "%" in groups["b"] else int(groups["b"])
        a = float(groups["a"]) if groups["a"] else 1.0
        if a < 1.0:
            logger.debug("converting rgba color to hex", extra={"color": css_color, "r": r, "g": g, "b": b, "a": a})
            return rgb_to_hex((r, g, b)) + f"{round(a * 255):02x}"
        else:
            logger.debug("converting rgb color to hex", extra={"color": css_color, "r": r, "g": g, "b": b})
            return rgb_to_hex((r, g, b))

    elif groups["hsl"]:
        h = int(groups["h"])
        s = int(groups["s"])
        l = int(groups["l"])
        a = float(groups["a"]) if groups["a"] else 1.0
        rgb_color = hsl_to_rgb((h, s, l))
        if a < 1.0:
            logger.debug("converting hsla color to hex", extra={"color": css_color, "hsl": (h, s, l), "a": a})
            return rgb_to_hex(rgb_color) + f"{round(a * 255):02x}"
        else:
            logger.debug("converting hsl color to hex", extra={"color": css_color, "hsl": (h, s, l)})
            return rgb_to_hex(rgb_color)

    # fmt: off
    elif groups["name"]:
        named_colors = {
            "aliceblue": "#f0f8ff",
            "antiquewhite": "#faebd7",
            "aqua": "#00ffff",
            "aquamarine": "#7fffd4",
            "azure": "#f0ffff",
            "beige": "#f5f5dc",
            "bisque": "#ffe4c4",
            "black": "#000000",
            "blanchedalmond": "#ffebcd",
            "blue": "#0000ff",
            "blueviolet": "#8a2be2",
            "brown": "#a52a2a",
            "burlywood": "#deb887",
            "cadetblue": "#5f9ea0",
            "chartreuse": "#7fff00",
            "chocolate": "#d2691e",
            "coral": "#ff7f50",
            "cornflowerblue": "#6495ed",
            "cornsilk": "#fff8dc",
            "crimson": "#dc143c",
            "cyan": "#00ffff",
            "darkblue": "#00008b",
            "darkcyan": "#008b8b",
            "darkgoldenrod": "#b8860b",
            "darkgray": "#a9a9a9",
            "darkgreen": "#006400",
            "darkkhaki": "#bdb76b",
            "darkmagenta": "#8b008b",
            "darkolivegreen": "#556b2f",
            "darkorange": "#ff8c00",
            "darkorchid": "#9932cc",
            "darkred": "#8b0000",
            "darksalmon": "#e9967a",
            "darkseagreen": "#8fbc8f",
            "darkslateblue": "#483d8b",
            "darkslategray": "#2f4f4f",
            "darkturquoise": "#00ced1",
            "darkviolet": "#9400d3",
            "deeppink": "#ff1493",
            "deepskyblue": "#00bfff",
            "dimgray": "#696969",
            "dodgerblue": "#1e90ff",
            "firebrick": "#b22222",
            "floralwhite": "#fffaf0",
            "forestgreen": "#228b22",
            "fuchsia": "#ff00ff",
            "gainsboro": "#dcdcdc",
            "ghostwhite": "#f8f8ff",
            "gold": "#ffd700",
            "goldenrod": "#daa520",
            "gray": "#808080",
            "green": "#008000",
            "greenyellow": "#adff2f",
            "honeydew": "#f0fff0",
            "hotpink": "#ff69b4",
            "indianred": "#cd5c5c",
            "indigo": "#4b0082",
            "ivory": "#fffff0",
            "khaki": "#f0e68c",
            "lavender": "#e6e6fa",
            "lavenderblush": "#fff0f5",
            "lawngreen": "#7cfc00",
            "lemonchiffon": "#fffacd",
            "lightblue": "#add8e6",
            "lightcoral": "#f08080",
            "lightcyan": "#e0ffff",
            "lightgoldenrodyellow": "#fafad2",
            "lightgray": "#d3d3d3",
            "lightgreen": "#90ee90",
            "lightpink": "#ffb6c1",
            "lightsalmon": "#ffa07a",
            "lightseagreen": "#20b2aa",
            "lightskyblue": "#87cefa",
            "lightslategray": "#778899",
            "lightsteelblue": "#b0c4de",
            "lightyellow": "#ffffe0",
            "lime": "#00ff00",
            "limegreen": "#32cd32",
            "linen": "#faf0e6",
            "magenta": "#ff00ff",
            "maroon": "#800000",
            "mediumaquamarine": "#66cdaa",
            "mediumblue": "#0000cd",
            "mediumorchid": "#ba55d3",
            "mediumpurple": "#9370db",
            "mediumseagreen": "#3cb371",
            "mediumslateblue": "#7b68ee",
            "mediumspringgreen": "#00fa9a",
            "mediumturquoise": "#48d1cc",
            "mediumvioletred": "#c71585",
            "midnightblue": "#191970",
            "mintcream": "#f5fffa",
            "mistyrose": "#ffe4e1",
            "moccasin": "#ffe4b5",
            "navajowhite": "#ffdead",
            "navy": "#000080",
            "oldlace": "#fdf5e6",
            "olive": "#808000",
            "olivedrab": "#6b8e23",
            "orange": "#ffa500",
            "orangered": "#ff4500",
            "orchid": "#da70d6",
            "palegoldenrod": "#eee8aa",
            "palegreen": "#98fb98",
            "paleturquoise": "#afeeee",
            "palevioletred": "#db7093",
            "papayawhip": "#ffefd5",
            "peachpuff": "#ffdab9",
            "peru": "#cd853f",
            "pink": "#ffc0cb",
            "plum": "#dda0dd",
            "powderblue": "#b0e0e6",
            "purple": "#800080",
            "rebeccapurple": "#663399",
            "red": "#ff0000",
            "rosybrown": "#bc8f8f",
            "royalblue": "#4169e1",
            "saddlebrown": "#8b4513",
            "salmon": "#fa8072",
            "sandybrown": "#f4a460",
            "seagreen": "#2e8b57",
            "seashell": "#fff5ee",
            "sienna": "#a0522d",
            "silver": "#c0c0c0",
            "skyblue": "#87ceeb",
            "slateblue": "#6a5acd",
            "slategray": "#708090",
            "snow": "#fffafa",
            "springgreen": "#00ff7f",
            "steelblue": "#4682b4",
            "tan": "#d2b48c",
            "teal": "#008080",
            "thistle": "#d8bfd8",
            "tomato": "#ff6347",
            "turquoise": "#40e0d0",
            "violet": "#ee82ee",
            "wheat": "#f5deb3",
            "white": "#ffffff",
            "whitesmoke": "#f5f5f5",
            "yellow": "#ffff00",
            "yellowgreen": "#9acd32",
        }
        logger.debug("parsing css color string", extra={"css_color": css_color})
        return named_colors[groups["name"].lower()]
    # fmt: on

    logger.error("invalid CSS color format", extra={"css_color": css_color})
    raise ValueError("Invalid CSS color format")


def replace_all(file, search_exp, replace_exp):
    for line in fileinput.input(file, inplace=1):
        line = re.sub(search_exp, replace_exp, line)
        sys.stdout.write(line)


def take_screenshot(html_file_path: str, css_file: str, output_file: str, driver: webdriver.Chrome) -> None:
    """
    Takes a screenshot of the given HTML file with the specified CSS applied.

    Args:
        html_file_path (str): Path to the HTML file or URL.
        css_file (str): Path to the CSS file to be applied.
        output_file (str): Path where the screenshot will be saved.
        driver (webdriver.Chrome): The Chrome WebDriver instance.
    """
    logger.info("taking screenshot for %s", css_file)
    try:
        # Open the HTML file or URL
        if html_file_path.startswith(("http://", "https://")):
            logger.info("opening URL: %s", html_file_path)
            driver.get(html_file_path)
        else:
            logger.info("opening file: %s", html_file_path)
            driver.get(f"file://{os.path.abspath(html_file_path)}")

        # Remove current theme.css
        remove_css_script = """
            var links = document.querySelectorAll("link[rel='stylesheet']");
            links.forEach(link => {
                if (link.href.includes('theme.css')) {
                    link.parentNode.removeChild(link);
                }
            });
        """
        logger.info("removing current theme.css")
        driver.execute_script(remove_css_script)

        with open(css_file, "r", encoding="utf-8") as f:
            logger.info("reading CSS file: %s", css_file)
            css_content = f.read()

        # Extract folder icon content
        css_parts = css_content.split(".foldericon {")
        css_head = css_parts[0]
        css_tail = css_parts[1].split("}", maxsplit=1)[1]
        folder_icon_content = css_parts[1].split("}", maxsplit=1)[0].strip()
        folder_icon_content = re.sub(r"/\*.*\*/", "", folder_icon_content)

        for match in re.finditer(r"content: (.*);", folder_icon_content):
            logger.info("found foldericon", extra={"foldericon": folder_icon_content})
            folder_icon_content = match.group(1).replace('"', "")
            break

        if "url" not in folder_icon_content:
            logger.info("Reading foldericon svg")
            with open(folder_icon_content.removeprefix("themes/"), "r", encoding="utf-8") as f:
                svg = f.read()
            if "svg.j2" in folder_icon_content:
                logger.info("foldericon in theme file is a jinja2 template")
                colorscheme = extract_colorscheme(css_file)
                for color_key, color_value in colorscheme.items():
                    svg = svg.replace(f"{{{{ {color_key} }}}}", color_value)
                logger.info("replaced colors in svg")
            svg = urllib.parse.quote(svg)

            css_content = f'{css_head}\n.foldericon {{\n  content: url("data:image/svg+xml,{svg}");\n}}\n{css_tail}'

        # Encode CSS content as Base64
        logger.info("encoding css content as base64")
        encoded_css = base64.b64encode(css_content.encode("utf-8")).decode("utf-8")

        # Inject CSS into HTML using JavaScript
        apply_css_script = f"""
            var style = document.createElement('style');
            style.innerHTML = atob('{encoded_css}');
            document.head.appendChild(style);
        """
        logger.info("injecting CSS into HTML")
        driver.execute_script(apply_css_script)

        # Wait for a while to ensure CSS is applied
        # time.sleep(1)

        # Move mouse to info
        logger.info("moving mouse to info")
        hoverable = driver.find_element(By.CLASS_NAME, "tooltip")
        webdriver.ActionChains(driver).move_to_element(hoverable).perform()

        # Capture screenshot
        logger.info("taking screenshot")
        driver.save_screenshot(output_file)
        logger.info("screenshot saved to %s", output_file)

    except Exception as e:
        logger.error("failed to take screenshot for %s: %s", css_file, e)


def create_preview(html_file_path: str, css_file: str, previews_folder: str):
    logger.info("creating preview for %s", css_file)
    out_file = os.path.basename(css_file).removesuffix(".css") + ".html"
    urllib.request.urlretrieve(html_file_path, os.path.join(previews_folder, out_file))
    basename = os.path.basename(css_file)
    path = css_file.removesuffix(basename)
    replace_all(
        os.path.join(previews_folder, out_file),
        r'\s*?href=".*theme.css"\s*?',
        f' href="file://{path}previews/{basename}"',
    )
    with open(css_file, "r", encoding="utf-8") as f:
        theme = f.read()
    split = theme.split(".foldericon {")
    split2 = split[1].split("}", maxsplit=1)
    themehead = split[0]
    themetail = split2[1]
    foldericon = split2[0].strip()
    foldericon = re.sub(r"/\*.*\*/", "", foldericon)
    for match in re.finditer(r"content: (.*);", foldericon):
        foldericon = match[1]
        foldericon = foldericon.replace('"', "")
        break
    if "url" in foldericon:
        logger.info("foldericon in theme file, using it")
        shutil.copyfile(css_file, os.path.join(path, "previews", basename))
        return
    with open(os.path.join(path, foldericon.removeprefix("themes/")), "r", encoding="utf-8") as f:
        logger.info("Reading foldericon svg")
        svg = f.read()
    if "svg.j2" in foldericon:
        logger.info("foldericon in theme file is a jinja2 template")
        colorscheme = extract_colorscheme(css_file)
        for color_key, color_value in colorscheme.items():
            svg = svg.replace(f"{{{{ {color_key} }}}}", color_value)
        logger.info("replaced colors in svg")
    svg = urllib.parse.quote(svg)
    if os.path.exists(os.path.join(path, "previews", basename)):
        os.remove(os.path.join(path, "previews", basename))
    with open(os.path.join(path, "previews", basename), "x", encoding="utf-8") as f:
        logger.info("writing theme file")
        f.write(themehead + '\n.foldericon {\n  content: url("data:image/svg+xml,' + svg + '");\n}\n' + themetail)
    logger.info("preview created for %s", css_file)


def write_readme(directory_path: str, themes: List[str]) -> None:
    """
    Writes the README file with previews of included themes.

    Args:
        directory_path (str): Path to the folder containing the themes and README.md.
        themes (List[str]): List of theme names.
    """
    readme_path = os.path.join(directory_path, "README.md")
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            logger.info("reading README.md", extra={"file": readme_path})
            readme = f.read()

        readme_head = readme.split("## Previews of included themes")[0]
        readme_head += "## Previews of included themes\n"
        readme_head += "".join([f"\n### {theme}\n\n![{theme}](screenshots/{theme}.png)\n" for theme in themes])

        with open(readme_path, "w", encoding="utf-8") as f:
            logger.info("writing README.md", extra={"file": readme_path})
            f.write(readme_head)

        logger.info("README.md updated with previews of included themes.")

    except FileNotFoundError:
        logger.error("README.md not found in %s", directory_path)
    except Exception as e:
        logger.error("failed to write README.md: %s", e)


def write_index(directory_path: str, themes: List[str]) -> None:
    with open(os.path.join(directory_path, "index.html"), "w", encoding="utf-8") as f:
        f.write(
            """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Themes</title>
</head>
<body>"""
        )
        for theme in themes:
            f.write(f'<a href="previews/{theme}.html">{theme}</a><br>\n')
        f.write("</body></html>")


def main(directory_path: str, html_file_path: str) -> None:
    """
    Main function to take screenshots for each CSS file in the folder and update the README.md.

    Args:
        directory_path (str): Path to the folder containing CSS files.
        html_file_path (str): Path to the HTML file or URL for rendering.
    """
    if not os.path.exists(directory_path):
        logger.error('Error: Folder path "%s" does not exist.', directory_path)
        return

    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode, no GUI
    chrome_options.add_argument("--window-size=1920,1080")  # Set window size to at least 1920x1080

    # Initialize Chrome WebDriver
    chromedriver_path = "/usr/bin/chromedriver"
    service = Service(chromedriver_path)
    logger.info("Using chromedriver at %s", chromedriver_path, extra={"chrome_options": chrome_options})
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        themes = []
        # Iterate over all files in the folder
        for filename in sorted(os.listdir(directory_path)):
            if filename.endswith(".css"):
                theme_name = os.path.splitext(filename)[0]
                themes.append(theme_name)
                css_file = os.path.join(directory_path, filename)
                output_file = os.path.join(directory_path, "screenshots", f"{theme_name}.png")
                previews_folder = os.path.join(directory_path, "previews")

                # Create screenshots folder if it doesn't exist
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                os.makedirs(previews_folder, exist_ok=True)

                # Take screenshot for this CSS file
                take_screenshot(html_file_path, css_file, output_file, driver)
                create_preview(html_file_path, css_file, previews_folder)

        # Write the README file with the new previews
        write_readme(directory_path, themes)
        write_index(directory_path, themes)

    finally:
        logger.info("closing chrome webdriver")
        driver.quit()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        logger.error("Usage: python script_name.py directory_path html_file_path")
    else:
        dir_path = sys.argv[1]
        html_path = sys.argv[2]
        logger.info("Starting script", extra={"directory_path": dir_path, "html_file_path": html_path})
        main(dir_path, html_path)
        logger.info("Done!", extra={"directory_path": dir_path})
