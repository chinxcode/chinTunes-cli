from setuptools import setup, find_packages

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="chintunes",
    version="1.0.0",
    description="High-Fidelity Multi-Platform Music Downloader & Studio Syncer",
    author="Chin",
    py_modules=["main"],
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "chintunes = syncer:cli",
            "chintune = syncer:cli",
        ],
    },
    python_requires=">=3.8",
)
