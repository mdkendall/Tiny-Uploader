![Tiny Uploader Logo](doc/images/uploader_logo.png)

THIS FORK IS A WORK IN PROGRESS. SEE UPSTREAM FOR A WORKING PROJECT.

This is a one click uploader tool to make the task of flashing ESP32 boards really simple. It is completely based on the <a href="https://github.com/tasmota/tasmotizer">Tasmotizer</a> project and uses the great <a href="https://github.com/espressif/esptool">ESPtool</a> from Espressif under the hood, and all required settings by default.

This document will guide you through the process of making your own one click uploader for your project.

## How to generate a Tiny Uploader

In order to provide always the last version of your firmware, the Tiny Uploader automatically downloads a firmware binary file from the internet and flashes it. So you will have to upload it somewhere and get an accessible URL.

 1. Clone the repository and make sure you have python3 and pip3 installed on your computer.
 2. Generate the header logo file: The header logo file is defined in binary on the Banner.py file. Thankfully we provide a script to generate that file from a png file. The original photo is a 558x300px PNG with transparency. Execute `python3 generateBanner.py <yourfile.png>` and it will generate a new file Banner.py for you.
 3. Edit the `firmwareURL.py` file and change the URL to the url of your firmware bin file.
 4. Your project is ready. Execute `pip3 install -r requirements.txt` followed by `python3 tasmotizer.py` and you can already test your Tiny Uploader.

## Executable file

As you might have noticed, the project contains many files and you need to execute it using python. This is probably not be the best idea if you want to publish your uploader and make it easy for your users to flash their boards. Thankfully there is a way to compile all your files into a single executable for Linux, Windows and Mac.

To do so, you need to install <a href="https://www.pyinstaller.org/">PyInstaller</a>. This tool will compress all your python files and generate a standalone executable file. Be aware that PyInstaller is not cross-platform, that means that the executable generated will only be compatible with the operating system you are executing it in. So if you want to compile it for Linux, Windows and Mac you will need a machine with each operating system to generate each executable.

Once you are on your target operating system, execute the following command and a single executable file will be generated for you.
```pyinstaller --name="My_Tiny_Uploader.exe" --windowed --onefile tasmotizer.py```

Alternatively you can also specify an icon file that you designed, so your executble looks even cooler with the following command:
```pyinstaller --name="My_Tiny_Uploader.exe" --windowed --onefile --icon=app.ico tasmotizer.py```

Be aware that icon files need to have specific characteristics for every operating system. Also, operating systems usually cache icons so once an icon is attached to your executable you will probably not see it change even if you execute the command a second time. For more info please refer to the PyInstaller documentation.

## Additional notes

Some web browsers will detect unsigned, newly generated executable files as potentially dangerous and might block them. Signing your executable might be a good idea so that users can also verify the authorsip.

## Screenshots

Coming soon

(c) 2021 Oscar <4m1g0> https://github.com/4m1g0
