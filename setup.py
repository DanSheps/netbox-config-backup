from setuptools import find_packages, setup

setup(
    name='netbox_config_backup',
    version='1.0.1',
    description='NetBox Configuration Backup',
    long_description='Plugin to backup device configuration',
    url='https://github.com/dansheps/netbox-config-backup/',
    download_url='https://github.com/dansheps/netbox-config-backup/',
    author='Daniel Sheppard',
    author_email='dans@dansheps.com',
    maintainer='Daniel Sheppard',
    maintainer_email='dans@dansheps.com',
    install_requires=[
        'importlib',
        'uuid',
        'dulwich',
        'pydriller',
        'netbox-plugin-extensions'
    ],
    packages=find_packages(),
    include_package_data=True,
    license='Proprietary',
    zip_safe=False,
    platform=[],
    keywords=['netbox', 'netbox-plugin'],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Framework :: Django',
        'Programming Language :: Python :: 3',
    ]
)