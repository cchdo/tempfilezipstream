import os.path

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()


requires = [
    'zipstream',
]


setup(
    name='tempfilezipstream',
    version='1.0',
    description='zipstream but for tempfiles',
    long_description=README,
    classifiers=[
        "Programming Language :: Python",
    ],
    author='CCHDO',
    author_email='cchdo@ucsd.edu',
    url='https://bitbucket.org/ghdc/tempfilezipstream',
    keywords='zip streaming',
    packages=find_packages(),
    test_suite='tests',
    install_requires=requires,
)
