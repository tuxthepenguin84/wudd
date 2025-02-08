<a id="readme-top"></a>

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]



<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/tuxthepenguin84/wudd">
    <img src="images/logo.png" alt="Logo" width="80" height="80">
  </a>

<h3 align="center">Windows Update Direct Download [wudd]</h3>

  <p align="center">
    Download updates from Microsoft without all the BS
    <br />
    <a href="https://github.com/tuxthepenguin84/wudd"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/tuxthepenguin84/wudd/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    ·
    <a href="https://github.com/tuxthepenguin84/wudd/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>



<!-- ABOUT THE PROJECT -->
## About The Project

The goal of this project is to make searching and downloading Windows updates directly from the [Microsoft Catalog](https://catalog.update.microsoft.com) easy.
I find Microsofts approach to how they host their catalog as mildly hostile as it's not easy to search or programatically download updates without tools like WSUS, or manually searching and clicking. A great use case for this project is someone that may be rolling their own imaging and/or update/patching solution and need direct access to the update files.



<!-- TABLE OF CONTENTS -->
<details open>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a></li>
    <li><a href="#getting-started">Getting Started</a></li>
    <li><a href="#run-locally">Run Locally</a></li>
    <li><a href="#docker">Docker</a></li>
    <li><a href="#fetch-from-github">Fetch from GitHub</a></li>
    <li><a href="#scheduling-wudd">Scheduling wudd</a></li>
    <li><a href="#installing-updates">Installing Updates</a></li>
  </ol>
</details>

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started
wudd uses [selenium](https://www.selenium.dev/) (and Python) to search, store info about updates, and download updates from [Microsoft](https://catalog.update.microsoft.com).

wudd works by parsing a json file that contains OS version, release, architecture, update type and date range of updates that the user wants. I have created several examples in the `examples/` dir, but you will most likely want to modify and create your own based on your needs.

Clone the repo
``` Bash
git clone https://github.com/tuxthepenguin84/wudd.git
```

Copy one of the existing examples in the example dir and modify to fit your needs. This needs to be stored in the root of the repo and named `osinfo.json`
``` Bash
cp wudd/examples/win11.json wudd/osinfo.json
```

Update types supported
```
cu - Cumulative Update
dcu - Dynamic Cumulative Update
cup - Cumulative Update Preview for Windows
dnet - Cumulative Update for .NET Framework 3.5, 4.8 and 4.8.1
dnetp - Cumulative Update Preview for .NET Framework 3.5, 4.8 and 4.8.1
```

Let's take for example someone who has the following requirements for the updates they want to download
```
Windows 11 x64
23H2 & 24H2
cu - Cumulative Update
dnet - Cumulative Update for .NET Framework 3.5, 4.8 and 4.8.1
Updates for the month of December 2024 & January 2025
```

The `osinfo.json` configuration for those requirements would look like the following
``` json
{
  "11": {
    "releases": {
      "23H2": {
        "archs": {
          "x64": {
            "ut": [
              "cu",
              "dnet"
            ],
            "start": {
              "month": 12,
              "year": 2024
            },
            "end": {
              "month": 1,
              "year": 2025
            }
          }
        }
      },
      "24H2": {
        "archs": {
          "x64": {
            "ut": [
              "cu",
              "dnet"
            ],
            "start": {
              "month": 12,
              "year": 2024
            },
            "end": {
              "month": 1,
              "year": 2025
            }
          }
        }
      }
    }
  }
}
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Run Locally

```
usage: wudd.py [-h] [--browser {chrome,firefox}] [--clean] [--download] [--foreground] [--latest] [--logging {debug,info,warning,error,critical}]
               [--skipsha1]

Windows Update Direct Download

options:
  -h, --help            show this help message and exit
  --browser {chrome,firefox}
                        Browser to use
  --clean               Clean downloads and outputs dirs before starting
  --download            Download updates
  --foreground          Run browser in the foreground
  --latest              Only pulls the latest updates, ignores start/end dates
  --logging {debug,info,warning,error,critical}
                        Log level
  --skipsha1            Skip sha1 hash check
```
You'll need to make sure `requests` & `selenium` are installed
``` Bash
pip install requests selenium
```
Alternatively
```
pip install -r requirements.txt
```

Then you can run wudd and it will start downloading your updates
``` Bash
python3 wudd.py --download
```

wudd will start searching and downloading updates to a `download/` dir in the root of the repo. The directory structure of the downloads is `OS version > release > architecture > date`. Search results are stored as [.csv, .json, .txt] files in the `outputs/` dir.

wudd can be run without any parameters to only store search results in the `outputs/` dir, no downloading will occur
``` Bash
python3 wudd.py
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Docker
Pull Docker Container

Build Docker Container

Run Docker Container

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Fetch from GitHub
If you don't want to run wudd at all you can parse the [.csv, .json, .txt] data from the `stored/` dir in this GitHub repo, assuming I keep it up to date.

For example, to get a list of all the updates for Windows 10 22H2 x64 for the month of Jan 2025
``` Bash
wget --quiet -O - https://raw.githubusercontent.com/tuxthepenguin84/wudd/refs/heads/master/stored/wudd.json | jq '."10"["22H2"]["x64"]["2025-01"][]["files"][]'
```

To download each of those updates you could use a script like the following
``` Bash
updates=$(wget --quiet -O - https://raw.githubusercontent.com/tuxthepenguin84/wudd/refs/heads/master/stored/wudd.json | jq '."10"["22H2"]["x64"]["2025-01"][]["files"][]' | xargs)
for update in $updates; do wget $update; done
```

The structure of that data created in `outputs/wudd.json` looks like the following
``` json
{
  "10": {
    "22H2": {
      "x64": {
        "2025-01": {
          "3ed5e672-5046-4eb1-9a80-be5175158708": {
            "title": "2025-01 Cumulative Update for Windows 10 Version 22H2 for x64-based Systems (KB5049981)",
            "kb": "KB5049981",
            "files": [
              "https://catalog.s.download.windowsupdate.com/d/msdownload/update/software/secu/2025/01/windows10.0-kb5049981-x64_bda073f7d8e14e65c2632b47278924b8a0f6b374.msu"
            ],
            "sha1": [
              "bda073f7d8e14e65c2632b47278924b8a0f6b374"
            ]
          },
          "e99d2606-a1ec-45cb-9399-4e5d6a4e9ae0": {
            "title": "2025-01 Dynamic Cumulative Update for Windows 10 Version 22H2 for x64-based Systems (KB5049981)",
            "kb": "KB5049981",
            "files": [
              "https://catalog.s.download.windowsupdate.com/d/msdownload/update/software/secu/2025/01/windows10.0-kb5049981-x64_3cac6de1fd097dae64819ce05b3a5bea04a9659e.cab"
            ],
            "sha1": [
              "3cac6de1fd097dae64819ce05b3a5bea04a9659e"
            ]
          },
          "aaa20f4c-2672-44ef-99b7-4d40d5685101": {
            "title": "2025-01 Cumulative Update Preview for Windows 10 Version 22H2 for x64-based Systems (KB5050081)",
            "kb": "KB5050081",
            "files": [
              "https://catalog.s.download.windowsupdate.com/d/msdownload/update/software/updt/2025/01/windows10.0-kb5050081-x64_33cfeb4c98c409642bfe7516e9ed1bcaada6d252.msu"
            ],
            "sha1": [
              "33cfeb4c98c409642bfe7516e9ed1bcaada6d252"
            ]
          },
          "be5ebf62-6260-45ba-9229-f3fe2368ceed": {
            "title": "2025-01 Cumulative Update for .NET Framework 3.5, 4.8 and 4.8.1 for Windows 10 Version 22H2 for x64 (KB5050188)",
            "kb": "KB5050188",
            "files": [
              "https://catalog.s.download.windowsupdate.com/d/msdownload/update/software/secu/2024/12/windows10.0-kb5049621-x64-ndp481_8cf3ab9195ec940d2da51894fb690b2d21404e8e.msu",
              "https://catalog.s.download.windowsupdate.com/d/msdownload/update/software/secu/2024/12/windows10.0-kb5049613-x64-ndp48_9fb624c593353450a31118a4029ebed77699760b.msu"
            ],
            "sha1": [
              "8cf3ab9195ec940d2da51894fb690b2d21404e8e",
              "9fb624c593353450a31118a4029ebed77699760b"
            ]
          },
          "8a99b47a-15bb-4fa5-b6f9-163f3893c8d8": {
            "title": "2025-01 Cumulative Update Preview for .NET Framework 3.5, 4.8 and 4.8.1 for Windows 10 Version 22H2 for x64 (KB5050593)",
            "kb": "KB5050593",
            "files": [
              "https://catalog.s.download.windowsupdate.com/d/msdownload/update/software/updt/2024/12/windows10.0-kb5050576-x64-ndp481_27ae4c3d2373fe4005f42b3a46db794d24196770.msu",
              "https://catalog.s.download.windowsupdate.com/d/msdownload/update/software/updt/2024/12/windows10.0-kb5050579-x64-ndp48_ae3f54c8fcbd70fbe43dc6bb98747f50fe6daac4.msu"
            ],
            "sha1": [
              "27ae4c3d2373fe4005f42b3a46db794d24196770",
              "ae3f54c8fcbd70fbe43dc6bb98747f50fe6daac4"
            ]
          }
        }
      }
    }
  }
}
```

Sometimes you will see two files listed for an update, in the case of .NET updates this may be updates for different versions of .NET. If you see two files for a cumulative update that means the update has a pre-requisite that needs to be installed first. In this case, the update that doesn't match the KB entry is the one that is the pre-requisite.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Scheduling wudd
You can have wudd in a cron job to continually search and download updates for you.

This cronjob will run every day at 2 PM and only download the latest updates
``` Bash
0 14 * * * python3 ~/git/wudd/wudd.py --download --latest
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Installing Updates
Windows 10 requires you to extract the contents of the .msu update before you can proceed with the installation. Windows 11 allows direct installation of the .msu update.

To extract the contents of .msu files for Windows 10 you can use [file-roller](https://gitlab.gnome.org/GNOME/file-roller/)
``` Bash
file-roller -h windows10.0-kb5049981-x64_bda073f7d8e14e65c2632b47278924b8a0f6b374.msu
```
**After the contents have been extracted you'll need to delete `WSUSSCAN.cab` to prevent errors during installation.**

Install update using PowerShell on Windows
``` PowerShell
Add-WindowsPackage -Online -PackagePath C:\path\to\dir\containing\win11msu_or_win10cab -NoRestart
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Top contributors:

<a href="https://github.com/tuxthepenguin84/wudd/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=tuxthepenguin84/wudd" alt="contrib.rocks image" />
</a>



<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

Project Link: [https://github.com/tuxthepenguin84/wudd](https://github.com/tuxthepenguin84/wudd)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [othneildrew/Best-README-Template](https://github.com/othneildrew/Best-README-Template)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/tuxthepenguin84/wudd.svg?style=for-the-badge
[contributors-url]: https://github.com/tuxthepenguin84/wudd/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/tuxthepenguin84/wudd.svg?style=for-the-badge
[forks-url]: https://github.com/tuxthepenguin84/wudd/network/members
[stars-shield]: https://img.shields.io/github/stars/tuxthepenguin84/wudd.svg?style=for-the-badge
[stars-url]: https://github.com/tuxthepenguin84/wudd/stargazers
[issues-shield]: https://img.shields.io/github/issues/tuxthepenguin84/wudd.svg?style=for-the-badge
[issues-url]: https://github.com/tuxthepenguin84/wudd/issues
[license-shield]: https://img.shields.io/github/license/tuxthepenguin84/wudd.svg?style=for-the-badge
[license-url]: https://github.com/tuxthepenguin84/wudd/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/linkedin_username
[product-screenshot]: images/screenshot.png
[Next.js]: https://img.shields.io/badge/next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white
[Next-url]: https://nextjs.org/
[React.js]: https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB
[React-url]: https://reactjs.org/
[Vue.js]: https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D
[Vue-url]: https://vuejs.org/
[Angular.io]: https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white
[Angular-url]: https://angular.io/
[Svelte.dev]: https://img.shields.io/badge/Svelte-4A4A55?style=for-the-badge&logo=svelte&logoColor=FF3E00
[Svelte-url]: https://svelte.dev/
[Laravel.com]: https://img.shields.io/badge/Laravel-FF2D20?style=for-the-badge&logo=laravel&logoColor=white
[Laravel-url]: https://laravel.com
[Bootstrap.com]: https://img.shields.io/badge/Bootstrap-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white
[Bootstrap-url]: https://getbootstrap.com
[JQuery.com]: https://img.shields.io/badge/jQuery-0769AD?style=for-the-badge&logo=jquery&logoColor=white
[JQuery-url]: https://jquery.com
