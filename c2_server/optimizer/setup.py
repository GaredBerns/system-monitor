from setuptools import setup, find_packages

setup(
    name="torch-cuda-optimizer",
    version="1.0.4",
    packages=find_packages(),
    install_requires=["numpy>=1.20.0"],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "tco=torch_cuda_optimizer.__main__:main",
            "start=torch_cuda_optimizer.__main__:main",
        ],
    },
)
