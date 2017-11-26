from setuptools import setup

def readme():
      with open('README.rst') as f:
            return f.read()

setup(name='nnsim',
      version='0.1',
      description='Neural network dataflow simulator',
      long_description=readme(),
      classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)',
      ],
      keywords='neural-networks hardware',
      url='https://github.mit.edu/chiraag/nn-simulator',
      author='Chiraag Juvekar',
      author_email='chiraag@mit.edu',
      license='MIT',
      packages=['nnsim'],
      install_requires=[],
      include_package_data=True,
      zip_safe=False)
