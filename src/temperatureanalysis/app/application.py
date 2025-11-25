from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QSettings, QTranslator, QLocale

import sys
import os

ORG_ID = "fsv-cvut"
APP_ID = "tunnel-fire"
ORG_DOMAIN = "https://people.fsv.cvut.cz/~stefarad/"

VISIBLE_ORG_NAME = "CTU in Prague, Faculty of Civil Engineering"
VISIBLE_APP_NAME = "TunnelFIRE"

_TRANSLATOR: QTranslator | None = None


def install_translator(app: QApplication, lang_code: str | None = None) -> bool:
    """Install the appropriate translator for the given language code."""
    from importlib.resources import files

    global _TRANSLATOR

    # Remove any existing translator
    if _TRANSLATOR is not None:
        app.removeTranslator(_TRANSLATOR)
        _TRANSLATOR = None

    # English is the default language, no need to load a translator
    if not lang_code or lang_code.lower() in ["en", "en_us", "en_gb"]:
        return True

    # Otherwise, try to load the corresponding .qm file
    base = files("temperatureanalysis.resources.i18n.qm")
    qm = base.joinpath(f"app_{lang_code}.qm")

    if not qm.is_file():
        return False

    ok = False
    tr = QTranslator(app)
    if tr.load(str(qm)):
        ok = app.installTranslator(tr)
        if ok:
            _TRANSLATOR = tr

    return ok


def create_app() -> QApplication:
    """Create and configure the QApplication instance."""
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    QCoreApplication.setOrganizationName(ORG_ID)
    QCoreApplication.setOrganizationDomain(ORG_DOMAIN)
    QCoreApplication.setApplicationName(APP_ID)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)

    app = QApplication(sys.argv)

    # Install translations
    # lang = QSettings().value("ui/language", "", type=str) or None
    # install_translator(app, lang)

    # Set the visible, translatable display name
    visible_name = QCoreApplication.translate("App", VISIBLE_APP_NAME)
    app.setApplicationDisplayName(visible_name)

    return app
