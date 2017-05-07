from distutils.core import setup

setup(name='Dotry',
      author='Corentin Cadiou',
      license='GNU General Public License v2.0',
      classifiers=[
          'Development Status :: 0.0.1 - Beta'
      ],
      version='0.0.1',
      description='Manage your scientific project',
      url='https://github.com/cphyc/dotry',
      install_requires=[
          'networkx',
          'matplotlib',
      ],
      packages=['dotry'],
      scripts=[
          'scripts/dotry',
          'scripts/dotry-init'
      ],
)
