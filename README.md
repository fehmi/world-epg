# World EPG

IPTVnator için `iptv-org/epg` kullanılarak GitHub üzerinde otomatik üretilen dünya yayın rehberi.

- EPG: https://fehmi.github.io/world-epg/guide.xml.gz
- Sıkıştırılmamış XML: https://fehmi.github.io/world-epg/guide.xml
- Kanal listesi: https://fehmi.github.io/world-epg/world.m3u
- Güncelleme ve kapsam raporu: https://fehmi.github.io/world-epg/status.json
- Çalıştırmalar: https://github.com/fehmi/world-epg/actions

Bu adresler ilk başarılı yayınlamanın ardından kullanılabilir.

## IPTVnator

Mevcut `iptv-org` listesinin ayrıntılarını açıp **EPG sources** alanına EPG adresini ekleyin ve **Save EPG sources** düğmesine basın. Kanal listesi olarak mevcut `https://iptv-org.github.io/iptv/index.m3u` adresi kullanılmaya devam edilebilir.

## Otomatik çalışma

GitHub Actions her gün 01:23 UTC'de (Türkiye saatiyle 04:23) tetiklenir; yoğunluk nedeniyle başlangıç gecikebilir. Projenin güncel sürümü alınır. Dünya kanal listesindeki kimlikler, projenin SITES.md dosyasında sağlam olarak işaretlenen kaynaklarla eşleştirilir. Varsa kanal başına iki ayrı kaynak denenir; sonuçlarda bir kaynak seçilerek mükerrer yayın akışları önlenir.

İki günlük rehber istenir. İşler 16 parçaya ayrılır; en fazla sekizi aynı anda çalışır. Bir kaynak grubu 10 dakikada tamamlanamazsa diğer gruplarla devam edilir. Sonuçlar birleştirilip GitHub Pages üzerinde yayınlanır. Hiç güncel program üretilemezse önceki yayın değiştirilmez. Başarılı güncellemelerin kapsam raporu depoya kaydedilir.

Mac'in açık kalması, Docker veya sürekli çalışan yerel sunucu gerekmez.

## Kapsam

Tüm ülkeleri içeren kanal listesi kullanılır. Her kanalın EPG verisi bulunmaz. İlk eşleştirme kontrolünde 11.353 kanal kimliğinin 4.121'i için doğrudan eşleşme bulundu; gerçek program verisi sunan kanal sayısı kaynakların durumuna bağlıdır. Güncel sayı `status.json` dosyasındaki `guide_channels` alanındadır. `mapped_channels` yalnızca eşleşme sayısıdır.

Kaynaklar kapanabilir, erişimi kısıtlayabilir veya yapılarını değiştirebilir. Üst projenin güncel sürümü otomatik alınır; bu işlem tamamen bakım gerektirmeyen bir hizmet garantisi değildir.

Kaynak kod: https://github.com/iptv-org/epg
