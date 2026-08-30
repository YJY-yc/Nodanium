# Nodanium #

<div align="center">

[![Release](https://img.shields.io/github/v/release/YJY-yc/Nodanium?style=for-the-badge&logo=github&color=4e7eb8)](https://github.com/YJY-yc/Nodanium/releases)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white&color=3776ab)](https://www.python.org/)
[![License](https://img.shields.io/github/license/YJY-yc/Nodanium?style=for-the-badge&label=License&color=green)](LICENSE)

[![GitHub Stars](https://img.shields.io/github/stars/YJY-yc/Nodanium?style=for-the-badge&logo=github&color=e3b341&label=Stars)](https://github.com/YJY-yc/Nodanium/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/YJY-yc/Nodanium?style=for-the-badge&logo=github&color=blue&label=Forks)](https://github.com/YJY-yc/Nodanium/network)
[![GitHub Issues](https://img.shields.io/github/issues/YJY-yc/Nodanium?style=for-the-badge&logo=github&color=d73a4a)](https://github.com/YJY-yc/Nodanium/issues)
[![GitHub Issues Closed](https://img.shields.io/github/issues-closed/YJY-yc/Nodanium?style=for-the-badge&logo=github&color=4caf50)](https://github.com/YJY-yc/Nodanium/issues)

[![Release Downloads](https://img.shields.io/github/downloads/YJY-yc/Nodanium/total?style=for-the-badge&logo=github&color=00c896&label=下载量)](https://github.com/YJY-yc/Nodanium/releases)

[![Windows](https://img.shields.io/badge/-Windows-0078d6?style=for-the-badge&logo=windows&logoColor=white)](#)
[![Linux](https://img.shields.io/badge/-Linux-fcc624?style=for-the-badge&logo=linux&logoColor=black)](#)
[![Commit Activity](https://img.shields.io/github/commit-activity/m/YJY-yc/Nodanium?style=for-the-badge&color=9b59b6)](https://github.com/YJY-yc/Nodanium/commits/main)
[![Last Commit](https://img.shields.io/github/last-commit/YJY-yc/Nodanium?style=for-the-badge&color=informational)](https://github.com/YJY-yc/Nodanium/commits/main)

</div>

## 一、项目介绍 ##
Nodanium(钒合金)是一个用Python开发的，跨Windows/Linux的网络工具。包括下载，爬取，分析，处理等网络操作。

## 二、功能介绍 ##
### 1. 下载功能
像大多数下载工具一样，Nodanium支持多线程下载，断点续传，批量下载等，并包含一个下载管理器。
- 多线程下载 
  多线程下载允许同时从多个线程下载文件，提高下载速度。并可以导出进度为``.ndf``脱机进度文件,以便继续下载。
- 批量下载 
  批量下载允许同时下载多个文件。从``.txt``文件或指定格式的``.json``文件中读取文件列表，批量下载。
- 站点式请求头
  在首选项的"请求头"页可按站点域名（支持 ``*.example.com`` 通配）配置条目式请求头与 Cookie。
  下载时自动按链接域名匹配并合并请求头，支持宏变量 ``{url} {host} {domain} {filename} {filepath}``，
  未命中站点时使用全局默认请求头，并可一键导出当前配置。
### 2. 网络工具类
　*网络工具* 是一些常用的工具集合
- 网页筛选
  网页筛选工具允许用户根据指定的条件筛选网页内容，例如爬取指定网页的下载链接，并支持一键批量下载。
- DNS编辑
  DNS编辑工具允许用户编辑本地DNS解析，例如添加自定义域名解析， 查看DNS缓存``仅Windows``,或重置host文件。
- Ping 
    Ping工具允许用户用图形化界面发送Ping请求。
- 文件服务
  文件服务工具允许用户在本地提供文件服务，将一个文件夹开放为网络共享，并允许其他设备访问，上传文件。
- 转发文件
    该工具允许用户将本地文件转发到指定端口，如HTML文件。
- 流量转盘
　该工具允许用户监测本地网络流量，包括上传流量和下载流量，网络速度和总上传／下载流量。

### 3. 管理功能类


- 端口管理器
  端口管理器工具允许用户管理本地端口，例如查看所有端口，关闭指定端口等。
- 下载管理
  下载管理工具允许用户管理下载的文件。

### 4. 插件
插件系统允许用户加载和使用外部插件，以扩展Nodanium的功能。将``.pyd``文件添加到插件目录``Plugins``目录下，即可在Nodanium中使用。

## 三、安装说明 ##
### 下载对应版本的Nodanium
在Windows上可下载``.zip`` ``.exe``格式的程序或安装包。
在Linux上可下载``.deb``格式的包或``.tar.gz``格式的压缩包。

> [!IMPORTANT]
> Linux 包基于 Python 3.12 及较新工具链构建，**最低要求 glibc ≥ 2.38**。
> 请优先使用与你的发行版匹配的 ``.deb`` 安装包；若使用 ``.tar.gz`` 压缩包，同样需要通过下方命令补齐依赖。

Linux依赖：`libwxgtk3.2-1t64`, `libc6`, `libgtk-3-0t64`, `libnotify4`

---

### Linux .deb 安装指南

#### 1. 安装 .deb 包

下载 ``Nodanium-<版本>-Linux-x64.deb`` 后，在对应的发行版执行：

**Ubuntu / Debian / Mint**（推荐，自动解析并安装缺失依赖）：
```bash
sudo apt install ./Nodanium-<版本>-Linux-x64.deb
```


**如果 apt 无法自动安装依赖（只安装主包）：**
```bash
sudo dpkg -i Nodanium-<版本>-Linux-x64.deb
sudo apt install -f   # 修复缺失的依赖及损坏的包
```


#### 2. 依赖说明与手动修复

安装/运行 ``Nodanium`` 需要以下依赖，**缺失时需手动安装**：

| 依赖包 | 作用 | 缺失时的表现 |
|---|---|---|
| `libc6` | C 标准库（glibc） | 无法启动，报 ``GLIBC_2.xx not found`` |
| `libgtk-3-0t64` | GTK3 图形库 | 窗口闪退，报 ``libgtk-3.so.0`` 找不到 |
| `libwxgtk3.2-1t64` | wxPython 依赖的 GTK 绑定 | 导入失败，报 ``找不到 wx`` 相关库 |
| `libnotify4` | 桌面通知 | 通知显示失败，其余功能不受影响 |

**`GLIBC_2.xx not found` 类错误**：说明系统 glibc 版本过低（本项目要求 **≥ 2.38**）。请升级系统或改用较旧的发行版（如 Debian 12、Ubuntu 22.04+）。

#### 3. 一键修复常见依赖

如果运行时报缺少共享库，可先执行以下命令补齐基础运行库：

```bash
# Ubuntu / Debian / Mint
sudo apt install -y libc6 libgtk-3-0t64 libwxgtk3.2-1t64 libnotify4

# Fedora / Rocky / CentOS
echo "libnotify.so.4" | xargs -r sudo dnf install -y libnotify || true
sudo dnf install -y glibc gtk3 wxGTK3
echo "如果系统没有 wxGTK3 包，请改用兼容的 wxGTK 版本或使用 .tar.gz 包"

# Arch / Manjaro
sudo pacman -S --needed glibc gtk3 wxgtk3 libnotify
```

#### 4. 查看依赖是否完整

```bash
dpkg -c Nodanium-<版本>-Linux-x64.deb              # 查看包内包含哪些文件
ldd $(which nodanium) 2>/dev/null | grep "not found"   # 检查缺失的共享库
ldd $(which nodanium) 2>/dev/null | grep wx        # 检查 wx 相关库是否解析到
```

若最后一行的 ``not found`` 有输出，说明仍有依赖未安装，按第 3 节补齐即可。

#### 5. 安装后使用

```bash
nodanium              # 启动图形界面
nodanium --version    # 查看版本
nodanium --help       # 查看帮助
```

若命令找不到，可确认安装位置：
```bash
which nodanium
# 部分安装包会把可执行文件放在 /usr/local/bin 或 /opt/nodanium/bin
```

---

## 四、CLI命令和程序目录 ##
### CLI选项:
```
  -v, --version           显示版本信息
  -h, --help              显示此帮助信息
  -c, --clear             清除数据目录
  -s, --silent            静默模式启动
  -r, --resume=<路径>     从 NDF/JSON 文件恢复下载
    --path=<保存路径>      覆盖保存目录（可选）
    --job=<线程数>         覆盖线程数（可选，0使用原设置）
    --cache=<缓存MB>      覆盖缓存大小（可选，0使用默认32MB）
    --header=<JSON头>     覆盖HTTP请求头（可选）
  --download              命令行下载模式
    --url=<链接>          下载链接
    --filename=<文件名>    保存文件名
    --path=<保存路径>      文件保存路径
    --job=<线程数>         下载线程数（默认16）
    --size=<包大小(B)>        每个线程下载的包大小（默认1MB）
    --header=<自定义头>    自定义HTTP头（默认空）
    --cache=<缓存时间>     缓存时间（默认10MB）
    --run=<自动运行>       是否运行（默认None）
    注意: --download 模式下，--url 和 --filename 为必填参数
  --old_download              命令行下载模式(旧版)
    --url=<链接>          下载链接
    --filename=<文件名>    保存文件名
    --path=<保存路径>      文件保存路径
    --job=<线程数>         下载线程数（默认16）

    注意: --old_download 模式下，--url 和 --filename 为必填参数  
```
### 程序目录：
%APPDATA%\Nodanium ``Windows``

~/.nodanium ``Linux``