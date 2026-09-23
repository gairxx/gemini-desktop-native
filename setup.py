from setuptools import setup

setup(
    name="gemini-desktop-native",
    version="1.0.0",
    description="Native Linux desktop client for Google Gemini (GTK4/WebKitGTK)",
    author="Gemini Desktop Native",
    license="MIT",
    python_requires=">=3.11",
    package_dir={"": "src"},
    py_modules=["main", "webview", "spotlight", "tray", "hotkey"],
    package_data={"": ["styles.css", "__init__.py"]},
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "gemini-desktop-native = main:main",
        ]
    },
    install_requires=[
        "pynput>=1.7.6",
    ],
    classifiers=[
        "Environment :: X11 Applications :: GTK",
        "Intended Audience :: End Users/Desktop",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
    ],
)