"""
================================================================================
 NATURAL GAS DATA TRANSFORMATION AND COMPILATION SYSTEM
================================================================================
 Application  : Data Transformation and Compilation of Natural Gas with GUI
 Module       : main.py  (Application Entry Point)
 Description  : This is the bootstrap module of the application. It is
                responsible for:
                    1. Verifying that all required third-party libraries
                       are installed (pandas, matplotlib, numpy).
                    2. Configuring the application-wide logging system so
                       that runtime events and errors are recorded to a
                       log file for engineering audit purposes.
                    3. Preparing the working directory structure used by
                       the application (exports, logs, temp).
                    4. Initializing the Tkinter root window with the
                       correct geometry, icon, title and theme.
                    5. Launching the main GUI (NaturalGasApp) which is
                       implemented in gui.py.
                    6. Providing a top-level exception handler so that any
                       unhandled error is logged and shown to the user in
                       a friendly dialog instead of crashing silently.

 Author       : Semester Project
 Version      : 1.0.0
================================================================================
"""

import os
import sys
import logging
import traceback
import tkinter as tk
from tkinter import messagebox
from datetime import datetime


# ==============================================================================
# 1. APPLICATION METADATA / GLOBAL CONSTANTS
# ==============================================================================
APP_NAME = "Natural Gas Data Transformation & Compilation System"
APP_SHORT_NAME = "NGDTC"
APP_VERSION = "1.0.0"
APP_ORGANIZATION = "Petroleum & Chemical Engineering Department"

# Default window geometry (professional engineering-software sizing)
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 750
WINDOW_DEFAULT_WIDTH = 1366
WINDOW_DEFAULT_HEIGHT = 800

# Directory structure used across the application
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

REQUIRED_DIRECTORIES = [LOG_DIR, EXPORT_DIR, ASSETS_DIR]

# Minimum required third-party packages for this application
REQUIRED_PACKAGES = {
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "numpy": "numpy",
}


# ==============================================================================
# 2. DIRECTORY BOOTSTRAP
# ==============================================================================
def ensure_directories():
    """
    Ensures that all directories required by the application exist before
    any module attempts to read from or write to them (e.g. log files,
    exported CSV/PNG results). Creates them silently if missing.
    """
    for directory in REQUIRED_DIRECTORIES:
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as exc:
            # If directories cannot be created, we still allow the app to
            # continue running from memory-only mode, but we print a
            # warning to stderr since the logger may not be ready yet.
            print(f"[WARNING] Could not create directory '{directory}': {exc}",
                  file=sys.stderr)


# ==============================================================================
# 3. LOGGING CONFIGURATION
# ==============================================================================
def configure_logging():
    """
    Configures a rotating-style, timestamped log file plus console output.
    Logging is used throughout the application (GUI actions, calculation
    results, import/export events, and unhandled exceptions) to give the
    project the traceability expected of professional engineering software.
    """
    log_filename = datetime.now().strftime("ngdtc_session_%Y-%m-%d_%H-%M-%S.log")
    log_filepath = os.path.join(LOG_DIR, log_filename)

    log_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if configure_logging() is ever called twice
    if root_logger.handlers:
        root_logger.handlers.clear()

    file_handler = logging.FileHandler(log_filepath, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.getLogger(__name__).info(
        "Logging initialized. Session log created at: %s", log_filepath
    )
    return log_filepath


# ==============================================================================
# 4. DEPENDENCY VERIFICATION
# ==============================================================================
def check_dependencies():
    """
    Verifies that all required third-party packages are importable before
    the GUI is constructed. If any package is missing, a clear message is
    printed (and, if Tkinter itself is available, shown in a dialog box)
    instructing the user how to install the missing dependency, and the
    application exits gracefully rather than raising a raw ImportError
    deep inside the GUI code.

    Returns:
        list[str]: A list of missing package names (empty if all present).
    """
    missing = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)
    return missing


def report_missing_dependencies(missing_packages):
    """
    Reports missing dependencies to the user via console and, if possible,
    a Tkinter message box, then terminates the application.
    """
    install_cmd = "pip install " + " ".join(missing_packages)
    message = (
        "The following required Python packages are missing:\n\n"
        f"  {', '.join(missing_packages)}\n\n"
        "Please install them using:\n\n"
        f"  {install_cmd}\n\n"
        "The application will now close."
    )

    print("=" * 78, file=sys.stderr)
    print("[FATAL] Missing required dependencies.", file=sys.stderr)
    print(message, file=sys.stderr)
    print("=" * 78, file=sys.stderr)

    try:
        # Tkinter is part of the standard library, so this should virtually
        # always succeed; we still guard it in case of a headless install.
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(f"{APP_NAME} - Missing Dependencies", message)
        root.destroy()
    except Exception:
        # If even Tkinter fails, we already printed the message to stderr.
        pass

    sys.exit(1)


# ==============================================================================
# 5. GLOBAL EXCEPTION HANDLING
# ==============================================================================
def install_global_exception_handler():
    """
    Installs a top-level exception hook so that any uncaught exception
    occurring anywhere in the application (including inside Tkinter
    callbacks that are not otherwise caught) is:
        1. Logged in full (with traceback) to the session log file.
        2. Presented to the user as a readable error dialog instead of a
           terminal stack trace, which is unacceptable in professional
           engineering software delivered to an end user.
    """
    logger = logging.getLogger("UnhandledException")

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Allow Ctrl+C to behave normally in console usage
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        formatted_traceback = "".join(
            traceback.format_exception(exc_type, exc_value, exc_traceback)
        )
        logger.critical("Unhandled exception occurred:\n%s", formatted_traceback)

        try:
            messagebox.showerror(
                f"{APP_NAME} - Unexpected Error",
                "An unexpected error occurred and has been logged.\n\n"
                f"Error Type : {exc_type.__name__}\n"
                f"Details    : {exc_value}\n\n"
                "Please check the log file in the 'logs' folder for full "
                "technical details, or contact the development team.",
            )
        except Exception:
            # If the GUI itself is broken, fall back to printing.
            print(formatted_traceback, file=sys.stderr)

    sys.excepthook = handle_exception

    def handle_tk_callback_exception(exc, val, tb):
        """
        Tkinter swallows exceptions raised inside widget callbacks by
        default and merely prints them. We override this behaviour on the
        Tk class itself so that every button click, menu action, or event
        handler in the entire GUI benefits from the same centralized
        logging + dialog reporting defined above.
        """
        handle_exception(exc, val, tb)

    tk.Tk.report_callback_exception = handle_tk_callback_exception


# ==============================================================================
# 6. SPLASH / LOADING WINDOW
# ==============================================================================
class SplashScreen:
    """
    A small, borderless splash window shown briefly while the main
    application initializes. This is purely cosmetic but is a standard
    feature of professional desktop engineering software (e.g. Aspen
    HYSYS, PIPESIM, PVTsim all show a splash screen on launch).
    """

    def __init__(self, parent_root):
        self.splash = tk.Toplevel(parent_root)
        self.splash.overrideredirect(True)
        self.splash.configure(bg="#0F2A3F")

        width, height = 520, 300
        screen_width = self.splash.winfo_screenwidth()
        screen_height = self.splash.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.splash.geometry(f"{width}x{height}+{x}+{y}")

        container = tk.Frame(self.splash, bg="#0F2A3F", highlightbackground="#1F9D8C",
                              highlightthickness=2)
        container.pack(fill="both", expand=True)

        tk.Label(
            container,
            text="⛽",
            font=("Segoe UI", 40),
            bg="#0F2A3F",
            fg="#1F9D8C",
        ).pack(pady=(30, 5))

        tk.Label(
            container,
            text="NATURAL GAS",
            font=("Segoe UI", 20, "bold"),
            bg="#0F2A3F",
            fg="#FFFFFF",
        ).pack()

        tk.Label(
            container,
            text="Data Transformation & Compilation System",
            font=("Segoe UI", 11),
            bg="#0F2A3F",
            fg="#B7C9D3",
        ).pack(pady=(0, 15))

        self.status_label = tk.Label(
            container,
            text="Initializing application modules...",
            font=("Segoe UI", 9, "italic"),
            bg="#0F2A3F",
            fg="#8FD9CC",
        )
        self.status_label.pack(pady=(20, 5))

        tk.Label(
            container,
            text=f"Version {APP_VERSION}  |  {APP_ORGANIZATION}",
            font=("Segoe UI", 8),
            bg="#0F2A3F",
            fg="#5E7A87",
        ).pack(side="bottom", pady=10)

        self.splash.update()

    def update_status(self, text):
        self.status_label.config(text=text)
        self.splash.update()

    def destroy(self):
        self.splash.destroy()


# ==============================================================================
# 7. APPLICATION LAUNCH SEQUENCE
# ==============================================================================
def launch_application():
    """
    Orchestrates the full startup sequence of the application in the
    correct order:
        1. Ensure required directories exist.
        2. Configure logging.
        3. Verify dependencies (pandas / matplotlib / numpy).
        4. Install the global exception handler.
        5. Create the hidden root Tk window + splash screen.
        6. Import and construct the main GUI (gui.NaturalGasApp).
        7. Reveal the main window and hand control to the Tk event loop.
    """
    ensure_directories()
    log_path = configure_logging()
    logger = logging.getLogger("Bootstrap")
    logger.info("Starting %s v%s", APP_NAME, APP_VERSION)

    missing = check_dependencies()
    if missing:
        logger.critical("Missing dependencies: %s", missing)
        report_missing_dependencies(missing)
        return  # unreachable, report_missing_dependencies() calls sys.exit()

    install_global_exception_handler()
    logger.info("Global exception handler installed.")

    # --- Root window setup -------------------------------------------------
    root = tk.Tk()
    root.withdraw()  # Hide main window until fully constructed

    try:
        root.title(f"{APP_NAME} v{APP_VERSION}")
    except Exception:
        pass

    # Center the main window on screen using the default dimensions
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    # Adapt the window to the available screen (leaves room for the menu
    # bar, title bar and taskbar so the status bar is never clipped on
    # small laptop displays such as 1366x768).
    win_w = min(WINDOW_DEFAULT_WIDTH, screen_width - 30)
    win_h = min(WINDOW_DEFAULT_HEIGHT, screen_height - 110)
    pos_x = max((screen_width - win_w) // 2, 0)
    pos_y = max((screen_height - win_h) // 2 - 30, 0)
    root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
    root.minsize(min(WINDOW_MIN_WIDTH, win_w), min(WINDOW_MIN_HEIGHT, win_h))

    # --- Splash screen -------------------------------------------------
    splash = SplashScreen(root)
    splash.update_status("Loading calculation engine...")
    root.after(200, lambda: None)  # allow splash to paint

    try:
        # NOTE: gui.py, calculations.py, gas_data.py, charts.py and
        # file_handler.py are separate modules of this project that will
        # be delivered in subsequent steps. main.py only orchestrates
        # startup and delegates all interface construction to gui.py so
        # that responsibilities remain cleanly separated (a standard
        # software-engineering practice expected in a graded project).
        splash.update_status("Loading gas component database...")
        from gui import NaturalGasApp  # local import: defined in gui.py

        splash.update_status("Building main interface...")
        app = NaturalGasApp(root, app_name=APP_NAME, app_version=APP_VERSION)

        splash.update_status("Ready.")
        root.after(400, splash.destroy)
        root.after(420, root.deiconify)

        logger.info("Main GUI constructed successfully. Entering main loop.")

    except ImportError as exc:
        splash.destroy()
        logger.critical("Failed to import GUI module: %s", exc)
        messagebox.showerror(
            f"{APP_NAME} - Startup Error",
            "The GUI module ('gui.py') could not be loaded.\n\n"
            f"Details: {exc}\n\n"
            "Make sure all project files (main.py, gui.py, calculations.py, "
            "gas_data.py, charts.py, file_handler.py) are located in the "
            "same folder."
        )
        root.destroy()
        return

    except Exception as exc:
        splash.destroy()
        logger.critical("Unexpected error during startup: %s", exc, exc_info=True)
        messagebox.showerror(
            f"{APP_NAME} - Startup Error",
            f"An unexpected error occurred while starting the application:\n\n{exc}"
        )
        root.destroy()
        return

    # --- Graceful shutdown handling -------------------------------------------------
    def on_closing():
        logger.info("Application closing by user request.")
        if messagebox.askokcancel(
            "Exit Application",
            "Are you sure you want to exit the Natural Gas Data "
            "Transformation & Compilation System?"
        ):
            logger.info("Session ended. Log file saved at: %s", log_path)
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # --- Enter the Tkinter event loop -------------------------------------------------
    root.mainloop()


# ==============================================================================
# 8. ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    launch_application()
