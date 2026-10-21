# Maintainer: Steven Eno <seno@pacificachristian.org>
pkgname=omacanvas
pkgver=0.1.0
pkgrel=1
pkgdesc="Locked-down Canvas LMS app for Omarchy (no general web browsing)"
arch=('any')
license=('MIT')
depends=('python' 'python-gobject' 'python-markdown' 'gtk3' 'webkit2gtk-4.1')
backup=('etc/omacanvas/config.json')
source=('omacanvas.py' 'turnin.py' 'config.json' 'org.pacificachristian.OmaCanvas.desktop' 'omacanvas.svg')
sha256sums=('SKIP' 'SKIP' 'SKIP' 'SKIP' 'SKIP')

package() {
  install -Dm755 omacanvas.py "$pkgdir/usr/share/omacanvas/omacanvas.py"
  install -Dm644 turnin.py "$pkgdir/usr/share/omacanvas/turnin.py"
  install -Dm644 config.json "$pkgdir/etc/omacanvas/config.json"
  install -Dm644 org.pacificachristian.OmaCanvas.desktop "$pkgdir/usr/share/applications/org.pacificachristian.OmaCanvas.desktop"
  install -Dm644 omacanvas.svg "$pkgdir/usr/share/icons/hicolor/scalable/apps/omacanvas.svg"
  install -dm755 "$pkgdir/usr/bin"
  ln -s /usr/share/omacanvas/omacanvas.py "$pkgdir/usr/bin/omacanvas"
}
