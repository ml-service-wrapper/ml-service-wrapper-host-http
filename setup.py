import os

from setuptools import find_namespace_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
   name='mlservicewrapper-host-http',
   use_scm_version = True,
   description='Host an mlservicewrapper service using HTTP',
   
   author='Matthew Haugen',
   author_email='mhaugen@haugenapplications.com',
   
   url="https://github.com/ml-service-wrapper/ml-service-wrapper-host-http",
   long_description=long_description,
   long_description_content_type="text/markdown",

   package_dir={"": "src"},
   packages=find_namespace_packages("src", include=['mlservicewrapper.*']),

   install_requires=[
      "mlservicewrapper-core>=0.5.0a0,<0.6",
      "starlette==0.13.7",
      "uvicorn",
      "gunicorn",
      "uvloop",
      "httptools"
   ],
   setup_requires=['setuptools_scm'],
   zip_safe=False,
   python_requires='>=3.6'
)
