from setuptools import setup, find_packages

setup(
    name='phnx',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'requests',
        'beautifulsoup4',
        'tqdm',
        'click',
    ],
    entry_points={
        'console_scripts': [
            'phnx=phnx.cli:cli',
        ],
    },
)
