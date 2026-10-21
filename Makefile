# Build an Arch package from the repo: `make pkg`, then `sudo pacman -U omacanvas-*.pkg.tar.zst`
pkg:
	rm -rf build && mkdir build
	cp PKGBUILD omacanvas.py turnin.py config.json data/* build/
	cd build && makepkg -fd && mv *.pkg.tar.zst ..

.PHONY: pkg
