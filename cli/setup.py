from setuptools import setup, find_packages

setup(
    name="gcploc",
    version="0.1.0",
    description="CLI for managing local GCP emulators (Pub/Sub, GCS, Cloud Tasks)",
    packages=find_packages(),
    py_modules=["gcploc"],
    python_requires=">=3.11",
    keywords=["gcp", "emulator", "docker-compose", "pubsub", "gcs", "cloud-tasks", "local-development"],
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Topic :: Utilities",
    ],
    install_requires=[
        "click>=8.0",
    ],
    entry_points={
        "console_scripts": [
            "gcploc=gcploc:cli",
        ],
    },
)
