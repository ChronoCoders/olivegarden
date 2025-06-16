#!/usr/bin/env bash
set -euo pipefail

# Whoami kontrolü
USER=$(whoami)
echo "Deploy script is running as $USER"

# Sistem paketleri yükleme fonksiyonu
install_packages() {
  sudo apt-get update
  sudo apt-get install -y nginx fail2ban docker.io docker-compose python3-pip
}

install_nginx() {
  sudo apt-get update
  sudo apt-get install -y nginx
  # SSL için gerçek sertifika yönetimini öneriyoruz
  # sudo certbot --nginx -d your.domain.com
}

# Uygulamayı ayağa kaldır
main() {
  install_packages

  # Docker-compose ile çalıştır
  docker-compose pull
  docker-compose up -d --remove-orphans

  # Nginx reload
  sudo systemctl reload nginx

  echo "Deployment tamamlandı."
}

main