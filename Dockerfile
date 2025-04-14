FROM debian:bullseye
# Set initial environment variables
ENV PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV LANG=C.UTF-8
# Install base dependencies
RUN set -eux; \
    apt-get clean && \
    apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    git \
    mercurial \
    openssh-client \
    subversion \
    procps \
    && rm -rf /var/lib/apt/lists/*
# Install development tools and SCM
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
    git \
    mercurial \
    openssh-client \
    subversion \
    procps \
    ; \
    rm -rf /var/lib/apt/lists/*
# Install build dependencies
RUN set -ex; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    bzip2 \
    default-libmysqlclient-dev \
    dpkg-dev \
    file \
    g++ \
    gcc \
    imagemagick \
    libbz2-dev \
    libc6-dev \
    libcurl4-openssl-dev \
    libdb-dev \
    libevent-dev \
    libffi-dev \
    libgdbm-dev \
    libglib2.0-dev \
    libgmp-dev \
    libjpeg-dev \
    libkrb5-dev \
    liblzma-dev \
    libmagickcore-dev \
    libmagickwand-dev \
    libmaxminddb-dev \
    libncurses5-dev \
    libncursesw5-dev \
    libpng-dev \
    libpq-dev \
    libreadline-dev \
    libsqlite3-dev \
    libssl-dev \
    libtool \
    libwebp-dev \
    libxml2-dev \
    libxslt-dev \
    libyaml-dev \
    make \
    patch \
    unzip \
    xz-utils \
    zlib1g-dev \
    ; \
    rm -rf /var/lib/apt/lists/*
# Install Python build dependencies
RUN set -eux && \
    apt-get update && \
    apt-get install -y --no-install-recommends libbluetooth-dev tk-dev uuid-dev && \
    rm -rf /var/lib/apt/lists/*
# Set Python-related environment variables
ENV GPG_KEY=A035C8C19219BA821ECEA86B64E628F8D684696D
ENV PYTHON_VERSION=3.10.16
ENV PYTHON_SHA256=bfb249609990220491a1b92850a07135ed0831e41738cf681d63cf01b2a8fbd1
# Build and install Python
RUN set -eux; \
    apt-get update && \
    apt-get install -y wget && \
    wget -O python.tar.xz "https://www.python.org/ftp/python/${PYTHON_VERSION%%[a-z]*}/Python-$PYTHON_VERSION.tar.xz" && \
    echo "$PYTHON_SHA256 *python.tar.xz" | sha256sum -c - && \
    mkdir -p /usr/src/python && \
    tar --extract --directory /usr/src/python --strip-components=1 --file python.tar.xz && \
    rm python.tar.xz && \
    cd /usr/src/python && \
    gnuArch="$(dpkg-architecture --query DEB_BUILD_GNU_TYPE)" && \
    ./configure \
    --build="$gnuArch" \
    --enable-loadable-sqlite-extensions \
    --enable-optimizations \
    --enable-option-checking=fatal \
    --enable-shared \
    --with-lto \
    --with-ensurepip && \
    nproc="$(nproc)" && \
    EXTRA_CFLAGS="$(dpkg-buildflags --get CFLAGS)" && \
    LDFLAGS="$(dpkg-buildflags --get LDFLAGS)" && \
    make -j "$nproc" \
    "EXTRA_CFLAGS=${EXTRA_CFLAGS:-}" \
    "LDFLAGS=${LDFLAGS:-}" && \
    rm python && \
    make -j "$nproc" \
    "EXTRA_CFLAGS=${EXTRA_CFLAGS:-}" \
    "LDFLAGS=${LDFLAGS:--Wl},-rpath='\$\$ORIGIN/../lib'" \
    python && \
    make install && \
    bin="$(readlink -ve /usr/local/bin/python3)" && \
    dir="$(dirname "$bin")" && \
    mkdir -p "/usr/share/gdb/auto-load/$dir" && \
    cp -vL Tools/gdb/libpython.py "/usr/share/gdb/auto-load/$bin-gdb.py" && \
    cd / && \
    rm -rf /usr/src/python && \
    find /usr/local -depth \
    \( \
    \( -type d -a \( -name test -o -name tests -o -name idle_test \) \) \
    -o \( -type f -a \( -name '*.pyc' -o -name '*.pyo' -o -name 'libpython*.a' \) \) \
    \) -exec rm -rf '{}' + && \
    ldconfig && \
    python3 --version && \
    rm -rf /var/lib/apt/lists/*
# Create Python command symlinks
RUN set -eux; \
    for src in idle3 pip3 pydoc3 python3 python3-config; do \
    dst="$(echo "$src" | tr -d 3)"; \
    [ -s "/usr/local/bin/$src" ]; \
    [ ! -e "/usr/local/bin/$dst" ]; \
    ln -svT "$src" "/usr/local/bin/$dst"; \
    done
# Install SQLite from source
RUN set -eux; \
    apt-get update --fix-missing; \
    apt-get upgrade -y; \
    curl -sL https://deb.nodesource.com/setup_20.x | bash -; \
    apt-get install -y --fix-missing --no-install-recommends \
    git build-essential gcc g++ sqlite3 libsqlite3-dev wget libgomp1 ffmpeg \
    python3 python3-pip python3-dev curl postgresql-client libnss3 libnspr4 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libatspi2.0-0 libxcomposite1 nodejs \
    libportaudio2 libasound-dev libreoffice unoconv poppler-utils chromium chromium-sandbox \
    unixodbc unixodbc-dev cmake openscad xvfb; \
    apt-get install -y gcc-10 g++-10; \
    update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-10 10; \
    update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-10 10; \
    awk '/^deb / && !seen[$0]++ {gsub(/^deb /, "deb-src "); print}' /etc/apt/sources.list | tee -a /etc/apt/sources.list; \
    apt-get update; \
    apt-get build-dep sqlite3 -y; \
    rm -rf /var/lib/apt/lists/*
RUN wget https://www.sqlite.org/2023/sqlite-autoconf-3420000.tar.gz && \
    tar xzf sqlite-autoconf-3420000.tar.gz && \
    if [ ! -d "/usr/lib/aarch64-linux-gnu/" ]; then mkdir -p /usr/lib/aarch64-linux-gnu/; fi && \
    cd sqlite-autoconf-3420000 && \
    ./configure && \
    make && make install && \
    cp /usr/local/lib/libsqlite3.* /usr/lib/aarch64-linux-gnu/ && \
    ldconfig && \
    cd .. && \
    rm -rf sqlite*
# Set additional environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    PLAYWRIGHT_BROWSERS_PATH=0 \
    HNSWLIB_NO_NATIVE=1 \
    LD_PRELOAD=libgomp.so.1 \
    LD_LIBRARY_PATH=/usr/local/lib64/: \
    DEBIAN_FRONTEND=noninteractive \
    CHROME_BIN=/usr/bin/chromium \
    CHROMIUM_PATH=/usr/bin/chromium \
    CHROMIUM_FLAGS=--no-sandbox
WORKDIR /zephyrex
# Install Python dependencies
COPY requirements.txt /zephyrex/requirements.txt
RUN pip install --upgrade pip && pip install -r ./requirements.txt
# Install Playwright
RUN playwright install-deps && \
    playwright install
COPY . /zephyrex
WORKDIR /zephyrex
EXPOSE 1996
ENTRYPOINT ["python3", "src/Server.py"]
