import sys


def main():
    from .app import BlenderLauncherApp

    app = BlenderLauncherApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
