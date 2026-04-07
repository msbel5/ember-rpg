# Ember RPG — Fallout 1 benzeri ama telif-safe yüzey ve UX PRD paketi

Bu belge, **Fallout 1’in birebir kopyası olmayan**, fakat onun bilgi yoğun, diegetic, sistemik ve oyuncu-ajansını öne çıkaran yüzey dilini Ember RPG için yeniden yorumlayan bir tasarım paketidir.

Amaç:
- Fallout 1’in hissini veren ama **görsel ve metinsel olarak özgün** bir shell kurmak
- Godot istemcisi ve deterministik backend için **LLM’e verilebilir PRD** üretmek
- Özellikle şu üç şeyi netleştirmek:
  1. ana shell / HUD
  2. diyalog + Ask About
  3. pause menu içindeki Ask DM / Think

---

## 1. Telif-safe sınırlar

### Kopyalanabilecek şeyler
- bilgi mimarisi
- ekranların görevleri
- menü ritmi
- düşük çözünürlükte okunabilir yoğun UI mantığı
- portreli / portresiz konuşma ayrımı
- keşifte karanlıktan açılan dünya haritası mantığı
- trade overlay mantığı
- kelime/konu tabanlı soru sorma sistemi
- alttan sabit komut rayı + üstte ana dünya görünümü mantığı

### Kopyalanmaması gereken şeyler
- Fallout’a ait özel isimler, markalar, cihaz isimleri, maskotlar
- paslı çelik + perçin + yeşil CRT kombinasyonunun birebir trade dress’i
- aynı buton adları, aynı yazı tonu, aynı sloganlar
- aynı frame oranları, aynı panellerin piksel dizilimi
- aynı karakter portre stili veya aynı açılar
- aynı intro kompozisyonları, aynı loading veya game over tabloları

### Ember için önerilen yeni yüzey teması
- **Malzeme dili:** isli bronz, koyu obsidyen, yanık deri, runik cam, kül altını
- **Işık dili:** zümrüt yerine kehribar + sönük mavi + kızıl kor parlamaları
- **Tipografi:** uzun dar endüstriyel font yerine kırık serif + mekanik sans karışımı
- **İkon dili:** retro-fütüristik maskot yerine simyasal işaretler, rünler, mühürler
- **Diegetic cihaz:** kol bilgisayarı değil, bileğe takılan rune-bracer / küçük katlanır codex / lodestone astrolabe

---

## 2. Ember için önerilen kavramsal sözlük

- Pip-Boy eşleniği → **Ember Codex** / **Ash Ledger** / **Rune Bracer**
- Skilldex eşleniği → **Discipline Panel** / **Field Arts**
- Tell Me About eşleniği → **Ask About** / **Probe Topic** / **Ask of**
- Review eşleniği → **Transcript** / **Conversation Log**
- Barter eşleniği → **Trade** / **Exchange** / **Offer Board**
- Karma eşleniği → **Reputation** / **Omen** / **Renown**
- Automap eşleniği → **Survey Map** / **Site Sketch**
- World Map eşleniği → **Realm Map** / **Ashlands Chart**
- Pause Menu’de Ask DM → **Ask DM** veya daha diegetic bir adla **Consult Fate**
- Pause Menu’de Think → **Think** / **Reflect** / **Thread Clues**

---

## 3. Fallout hissinin özü: kopya değil, soyut tasarım kuralları

1. Oyunun ana dünyası her zaman baskındır; menüler onun üstüne cihaz gibi açılır.
2. Her bilgi ekranı oyunun dünyasında “bir araç” gibi davranır.
3. Aynı ekran hem estetik hem sistemik olmalıdır; dekoratif ama tamamen okunabilir.
4. Oyuncu bir anda yalnızca bir ana problem çözmelidir: konuşma, eşya, harita, karakter, dinlenme.
5. Düşük çözünürlükte okunabilirlik için bloklar büyük, yazılar sade, bilgi hiyerarşisi sert olmalıdır.
6. UI hiçbir zaman tam modern olmamalı; biraz mekanik gecikme, açılır-kapanır panel hissi, tıklama ağırlığı olmalı.
7. Diyalog sadece seçenek listesi değil, dünya bilgisini toplamanın da yolu olmalıdır.
8. Keşif haritası bir “GPS” değil, eksik bilgiyle çalışan bir sefer planlama ekranı olmalıdır.
9. İnventory sadece liste değil, karakterin fiziksel taşıma ve kuşanım durumunu göstermelidir.
10. Her ekran bir “oyuncu kararı” üretmelidir. Sadece bilgi sunmamalı.

---

## 4. Ekran kataloğu — telif-safe yazılı tarifler

Aşağıdaki bölüm, Fallout 1’in ana yüzey mantığını Ember’e uyarlanmış şekilde **ekran ekran** tarif eder.

---

## 4.1 Başlık / Ana Menü

### Amaç
Oyuncuya daha ilk saniyede “yoğun ama ağırbaşlı CRPG” hissi vermek.

### Ember yorumu
- Sol tarafta veya tam ortada oyunun yeni ikonografisi: büyü-zırh sentezi taşıyan **özgün bir figür**.
- Sağda ya da ortada dikey komut listesi.
- Arka planda hafif parallax: uzak kuleler, kırık manastırlar, kızıl kül, ley-line parlamaları.
- Ses tasarımı: düşük frekanslı uğultu + metal değil daha çok taş/rune titreşimi.

### Buton seti
- Continue Chronicle
- New Chronicle
- Load Chronicle
- Prologue
- Codex / Lore
- Settings
- Credits
- Exit

### Telif-safe not
- Dev zırhlı kask yerine **ember-mask**, **rune helm**, **obsidian sentinel**, **bone-plate knight** gibi yeni bir ikon kullan.
- Menü paneli perçinli çelik olmasın; mühürlenmiş taş, bronz ray veya açılır kitabî tabla olsun.

### Wireframe
```text
+--------------------------------------------------------------+
|                      EMBER RPG LOGO                          |
|                                                              |
|      [hero art / sentinel silhouette / burning tower]        |
|                                                              |
|                           [Continue]                         |
|                           [New Chronicle]                    |
|                           [Load Chronicle]                   |
|                           [Prologue]                         |
|                           [Codex]                            |
|                           [Settings]                         |
|                           [Credits]                          |
|                           [Exit]                             |
+--------------------------------------------------------------+
```

---

## 4.2 Karakter Seçimi / Başlangıç Dossier Ekranı

### Amaç
Yeni oyuna girmeden önce oyuncuya iki kapı açmak:
- hazır arketip seç
- sıfırdan kendi karakterini üret

### Ember yorumu
- Ekranın üst kısmında seçili adayın yüzü veya büstü.
- Sol blokta temel nitelikler.
- Sağ blokta kısa biyografi, oyun stili özeti ve başlangıç ekipmanı.
- Altta üç ana buton:
  - Take / Select
  - Modify / Inspect
  - Create New

### İçerik
- 3–4 hazır karakter:
  - spellblade
  - relic hunter
  - court emissary
  - ash scout
- Her biri için:
  - oyun stili etiketi
  - risk seviyesi
  - önerilen oyuncu profili

### Kritik tasarım kararı
Bu yüzey ile daha sonra oyun içindeki **karakter sayfası aynı aileden** olmalı. Yani creation ve in-game sheet ortak bir görsel dil paylaşmalı.

---

## 4.3 Karakter Yaratma + Oyun İçi Karakter Sayfası (Unified Dossier)

### Tasarım hedefi
Fallout 1’de creation ve later character sheet aynı bilgi mantığını paylaşıyor. Ember’de bunu daha da ileri götür:

**tek surface, iki mod:**
- creation mode
- runtime mode

### Sol kolon
- Attributes
- Derived stats
- resistances
- initiative / AP / carry / spell focus

### Orta kolon
- tam vücut paper doll
- body armor zones:
  - head
  - face
  - neck
  - shoulders
  - chest
  - arms
  - hands
  - belt
  - legs
  - feet
- ayrıca magic attunement slots:
  - sigil slot
  - charm slot
  - relic slot
  - focus slot

### Sağ kolon
- skills / disciplines / spells listesi
- selected traits / vows / scars / omens
- XP, level, next level
- current injuries
- fame / suspicion / faction standing

### Alt bilgi kartı
Sağ alttaki kart ya da bilgi penceresi, seçilen her alan için açıklama göstermeli.
Bu Fallout’taki “bilgi kartı” mantığını sürdürür ama özgünleşir.

### Creation mode alanları
- isim
- geçmiş / origin
- class / calling
- attributes dağıtımı
- 3–5 tag skill / focus discipline
- 0–2 trait / flaw
- başlangıç büyüsel yatkınlık

### Runtime mode ek alanları
- injuries panel
- learned spells
- discovered passives
- reputation ledger
- perk-like advancement seçimleri

### Wireframe
```text
+--------------------------------------------------------------------------------+
| NAME / TITLE                                                                   |
|--------------------------------------------------------------------------------|
| ATTRIBUTES         | PAPER DOLL / BODY SLOTS         | SKILLS / SPELLS         |
| MIG  8 (+1)        | [head] [neck]                   | Blades        42         |
| AGI 12 (+2)        | [shoulders]                     | Fire Rite     31         |
| END 10 (+0)        | [chest]                         | Lore          55         |
| WIT 11 (+1)        | [arms] [hands]                  | Speech        40         |
| WIL 14 (+2)        | [belt]                          | Lockwork      18         |
| PRE  9 (+0)        | [legs] [feet]                   | ...                       |
| LUCK 7 (-1)        | [sigil] [charm] [relic] [focus] |                          |
|--------------------------------------------------------------------------------|
| MEDICAL / STATUS   | XP / LEVEL / OATHS / REPUTATION  | INFO CARD               |
|--------------------------------------------------------------------------------|
| [Back] [Perks] [Traits] [Done]                                                  |
+--------------------------------------------------------------------------------+
```

---

## 4.4 Ana Oyun Görünümü + Alt Komut Rayı

### En kritik yüzey
Fallout 1 hissini en çok veren şey: **üstte dünya, altta sabit komut sistemi**.

### Ember yorumu
- Ekranın üst %72–78’i dünya görünümü.
- Alt %22–28’i sabit **instrument rail**.
- Bu rail HUD değil, dünyaya ait bir cihaz hissi verir.

### Sol alt monitör
- hover açıklaması
- kısa olay logu
- combat sonuçları
- skill check feedback
- inspect text

### Orta bölüm
- primary hand slot
- secondary hand slot
- quick spell / mantra slot
- AP / focus pips
- ammo / charge / durability / cast cost

### Sağ bölüm
- combat state button
- character
- inventory
- map
- codex
- field arts
- options

### Sayacılar
- HP
- Ward / Shield
- Armor
- Stamina / Focus
- Encumbrance uyarısı

### Telif-safe farkı
- Fallout’taki perçinli metal bar yerine, yatay **ritual instrument bench** gibi görün.
- Paneller smoked-glass + bronze frame + faint runic seams taşısın.

### Davranış kuralları
- dünya görünümü asla tamamen kapanmamalı; sadece tek ana modal açılmalı
- her ana buton tek bir büyük overlay açmalı
- ESC daima modal kapatma hiyerarşisine uymalı

---

## 4.5 İmleç Modları ve Eylem Şeridi

### Amaç
Fare ile yalnız tıklama değil, bağlamsal fiil seçimi.

### Ember yorumu
İki ana mod:
- move cursor
- command cursor

Command cursor bir objenin üstünde bekleyince varsayılan fiili gösterir:
- talk
- open
- search
- use
- attack
- examine

Tıklamayı basılı tutunca küçük bir **verb strip** açılır.
Bu strip dikey olabilir ama Fallout’taki birebir ikon setini kopyalamamalıdır.

### Önerilen fiiller
- Interact
- Examine
- Speak
- Search
- Use Tool
- Cast
- Pick Up
- Rotate / Face

### Hedefleme modu
- düşman üstünde hit chance
- range band
- cover
- resist icon
- body zone preview

### Magic entegrasyonu
Hedefleme modunda sadece saldırı değil:
- cone
- line
- self aura
- placed sigil
- chain target

---

## 4.6 Combat Açılımı

### Amaç
Normal real-time exploration’dan turn tabanlı veya paused tactical moda geçişin hissedilmesi.

### Ember yorumu
Combat başlayınca alt rayın sağ kanadı açılır:
- attack mode
- spell mode
- target zone
- defend
- wait
- end turn

### Görsel dil
- exploration’da sakin amber ışık
- combat’ta AP/focus pips daha sert ve parlak
- düşman sırası ile oyuncu sırası ayrı renk dillerine sahip olabilir

### Body zone sistemi
Çünkü “armor her yere olacak” dedin; o yüzden combat hedefleme ve character sheet bunu desteklemeli.

#### Hedef bölgeler
- head
- torso
- main arm
- off arm
- legs
- carried focus

#### Sonuçlar
- armor penetration
- blunt trauma
- bleed
- fracture
- cast disruption
- shield break
- stance break

### Combat log
Sol monitörde kısa ve okunur:
- miss
- graze
- hit
- crit
- blocked
- resisted
- armor absorbed
- limb impaired
- spell fizzled

---

## 4.7 Loot / Corpse Search / Container Search

### Amaç
Dünya ile inventory arasında küçük ama yoğun bir köprü.

### Ember yorumu
İki kolonlu küçük modal:
- sol: oyuncu envanteri
- sağ: ceset / sandık / raf / düşen loot
- ortada transfer alanı veya hızlı al butonları

### Özellikler
- take all
- quick sort
- compare equipped
- stack split
- inspect on hover
- unread recipe / key item highlight

### Kritik davranış
Loot modalı inventory’nin küçültülmüş türevi olmalı. Yani yeni bir sistem gibi hissettirmemeli.

---

## 4.8 Inventory / Equipment

### Tasarım mantığı
Bu ekran “liste” değil, oyuncunun fiziksel taşıma ve giyinme durumudur.

### Sol şerit
- backpack item list
- stacked items
- filters:
  - weapons
  - armor
  - reagents
  - tools
  - books
  - keys
  - junk

### Orta büyük alan
- karakter paper doll
- gear slots
- weapon slots
- active consumable slots
- quick access belt

### Sağ bilgi kartı
- item art silhouette
- name
- rarity
- damage / defense profile
- spell attunement
- weight
- value
- tags
- lore snippet

### Alt satır
- total carry
- overload threshold
- gold / barter value / favors
- compare toggle
- identify status

### Magic-aware armor sistemi
Her armor parçası için:
- physical armor
- elemental resist profile
- noise / stealth penalty
- spell interference
- sigil conductivity
- movement cost

### Çok önemli
Fallout’taki damage type okuması iyi; Ember bunu daha ileri taşı:
- steel
- fire
- frost
- lightning
- acid
- rot
- spirit
- void

---

## 4.9 Field Arts / Skill Panel

### Amaç
Aktif kullanılan becerileri tek yerde toplamak.

### Ember yorumu
Skilldex benzeri ama daha geniş bir yüzey:
- stealth
- lockwork
- trapcraft
- medicine
- repair
- lore
- commune
- tracking
- arcana

### Etkileşim
- tıklayınca hedef isteyen beceri target mode’a geçer
- toggle beceriler (sneak, detect, ward sense) açık kalır
- sayı tuşlarına atanır
- combat içinde AP/focus maliyeti görünür

### Görünüm
Liste + ikon değil; kategori kartları + hızlı kısayol numarası.

---

## 4.10 Ember Codex / Ash Ledger (PIPBoy eşleniği)

### Amaç
Oyuncunun dış dünya bilgisi, görevleri, haritaları ve zaman kontrolünü diegetic bir cihazda toplamak.

### Ana sekmeler
- Status
- Quests
- Maps
- Rumors
- Archive
- Rest

### Status
- aktif sorunlar
- wounds
- disease / curse
- temporary effects
- faction heat
- hunger / fatigue / mana saturation

### Quests
- aktif objective listesi
- completed objective strike-through
- location bazlı gruplanmış görevler
- urgency işareti

### Maps
- local automap listesi
- katlar / bölgeler
- discovered entrances
- named rooms

### Rumors
- teyitsiz bilgi
- kimden duyuldu
- güven seviyesi
- ilgili yer / kişi / öğe

### Archive
- cutscene equivalent kayıtları
- bulunan metinler
- deciphered tablets
- audio logs yerine rune echoes / memory shards

### Rest
- 10 dk / 30 dk / 1 saat / 3 saat / geceye kadar / iyileşene kadar
- iyileşme tahmini
- nöbet riski
- güvenli değil uyarısı

---

## 4.11 Local Automap

### Amaç
Bulunduğun alanın zihinsel krokisini vermek, tam GPS vermemek.

### Ember yorumu
- sadece keşfedilmiş duvarlar, odalar, koridorlar, kapılar
- isteğe bağlı entity overlay
- floor selector
- current position marker
- discovered hazard markers
- ritual nodes / locked seals / stairs / lifts / portals

### İyi davranışlar
- automap, ana dünyadan daha soyut olmalı
- fazla sanat değil, bilgi odaklı olmalı
- oyuncu her şeyi değil, gördüğünü ve haritaladığını görmeli

---

## 4.12 World Map / Realm Map / Town Map

### En kritik CRPG hissi yüzeyi

### Ember yorumu
- başlangıçta büyük ölçüde karanlık / sisli
- görülen ama gidilmeyen yerler yarı görünür
- gidilen yerler netleşir
- sağ tarafta bilinen lokasyon listesi
- üst sağda zaman, tarih, ay evresi, mevsim, hava kırıntısı
- alt ya da yan panelde terrain cost, encounter risk, travel ETA

### Tıklama davranışı
- boşluğa tıkla → keşif rotası
- bilinen yere tıkla → doğrudan seyahat
- path preview göster
- risk iconları göster

### Random encounter sistemi
Yolda kesilebilir:
- haydut baskını
- yaratık izleri
- büyü anomalisi
- tüccar kafilesi
- gömülü kalıntı
- hikâye olayı

### Town map
- bir ana yerin içinde alt giriş noktaları
- district / room / gate / vault / market / chapel düğümleri
- keşfettikçe artan marker sayısı

### Ember’e özgü ek katmanlar
- ley lines
- corruption spread
- faction patrol zones
- weather fronts
- beacon networks

---

## 4.13 Chat Barks (kısa konuşma)

### Amaç
Her NPC’yi büyük diyalog ekranına taşımadan canlı hissettirmek.

### Ember yorumu
- baş üstü tek satır / iki satır konuşma
- renk ile duygusal ton
- combat taunt varyantları
- guard warning
- merchant bark
- villager rumor hint

### Kural
Önemsiz NPC’ler ya sadece bark verir ya da çok kısa branşlı konuşma açar.
Bu sayede önemli NPC’lerin büyük diyalog ekranı daha değerli hissedilir.

---

## 4.14 Extended Dialogue Overlay

### Amaç
Oyuncu ile önemli NPC arasında tam karar yüzeyi açmak.

### Layout
- sol üst: portre veya sahne crop
- orta üst: NPC metni
- alt: cevap seçenekleri
- sağ şerit veya alt butonlar: Trade, Ask About, Review, Leave

### Portreli / portresiz ayrımı
- named important NPC → portre veya yüz yakın planı
- generic NPC → sahneden alınmış framed crop

### Seçenek dili
Cevapların sadece metin değil **ton etiketi** olmalı:
- [Direct]
- [Soft]
- [Lie]
- [Threaten]
- [Charm]
- [Lore]
- [Faith]
- [Arcana]
- [Trade]

### Gizli check mantığı
- bazı cevaplar görünür ama risk taşır
- bazı cevaplar stat/skill yüzünden görünmez
- bazıları belli eşya / bilgi / reputasyon olmadan açılmaz

### Kritik not
Ekran oyuncuya sadece “ne söyleyeceğini” değil, “ne araştırabileceğini” de söylemeli.

---

## 4.15 Transcript / Review

### Amaç
Aktif konuşmanın log’unu görmek.

### Ember yorumu
- aynı conversation içinde transcript açılabilir
- NPC ve oyuncu satırları ayrı stil
- kaydırılabilir
- önemli satırlara pin atılabilir

### İleri öneri
- transcript içindeki proper noun’lar tıklanabilir topic chip’e dönüşebilir
- buradan doğrudan Ask About açılabilir

---

## 4.16 Trade Overlay

### Amaç
Konuşmanın içinden doğal şekilde alışverişe geçmek.

### Layout
- sol: oyuncu envanteri
- sağ: tüccar envanteri
- orta: offer board
- alt: teklif dengesi, merchant mood, confirm / cancel

### Değer modeli
- para
- takas değeri
- borç / favor
- faction discount
- relationship modifier
- appraisal uncertainty

### Magic özel durumları
- identify edilmemiş item’lar
- cursed item’lar
- reagent bundle’ları
- soulbound / attuned item’lar trade edilemez ya da maliyetlidir

### Merchant personality etkisi
- cimri
- sabırlı
- koleksiyoncu
- kutsal eşya avcısı
- silah sever
- yabancılara güvensiz

Bu kişilik yalnız fiyatı değil, hangi item’a ilgi duyduğunu da etkiler.

---

## 4.17 Ask About (Fallout’taki Tell Me About mekanik karşılığı)

### Bu sistem Ember’in kalbi olmalı

### Tasarım amacı
Oyuncu sadece hazır diyalog seçenekleriyle sınırlı kalmasın; duyduğu bir isim, yer, nesne, tarikat, büyü, olay veya söylenti hakkında **özgürce soru sorabilsin**.

### UI akışı
1. Extended dialogue açık.
2. Oyuncu **Ask About** düğmesine basar.
3. Küçük topic modalı açılır.
4. Üstte input alanı, altında bilinen topic chip’leri.
5. Oyuncu ya yazar ya chip seçer.
6. NPC:
   - biliyorsa cevap verir
   - kısmen biliyorsa rumor verir
   - bilmiyorsa uygun fallback söyler
   - söylemek istemiyorsa disposition check uygulanır

### Topic chip kaynakları
- bu konuşmada geçen proper noun’lar
- jurnalden bilinen isimler
- bulunduğun bölgeyle ilgili yerler
- aktif görev nesneleri
- party’nin taşıdığı önemli eşyalar

### Cevap tipleri
- fact
- rumor
- redirect (“bunu X’e sor”)
- refusal
- lie
- gated answer (skill / trust / faction)
- world state dependent answer

### Neden çok güçlü
Bu sistem oyuncuda “dünya gerçekten biliyor” hissi yaratır. Dallı menüye göre çok daha keşif odaklıdır.

### Telif-safe not
Aynı mekanik korunabilir ama label ve görsel sunum farklı olmalı.

---

## 4.18 Pause Menu

### Amaç
Oyuncuya oyundan kopmadan yönetim yüzeyi sunmak.

### Ember yorumu
- Resume
- Save
- Load
- Settings
- Controls
- Journal / Codex
- Ask DM
- Think
- Exit to Title

### Güvenli alan kuralı
- combat’ta bazı seçenekler kilitli
- dialogue sırasında bazı seçenekler kısıtlı
- world travel sırasında save/load davranışı net tanımlı

---

## 4.19 Ask DM

### Tasarım hedefi
Bu sistem **oyunun hakikatini anlatan serbest bir chatbot** olmamalı.
Deterministik backend’li bir oyunda bu çok tehlikeli olur.

Ask DM, oyuncuya şu çerçevede yardım etmeli:
- şu an ne biliyorum?
- bu bölgede ne yapabilirim?
- kiminle konuşmam mantıklı?
- hangi ipuçlarını kaçırıyorum?
- elimdeki görev için en muhtemel bir sonraki adım ne?

### Kural
Ask DM sadece şunlardan cevap üretebilir:
- discovered facts
- active objectives
- visible interactables
- learned topics
- known NPC relations
- known blockers
- already unlocked lore

### Asla yapmamalı
- henüz keşfedilmemiş gizemi doğrulamak
- hidden trigger reveal etmek
- oyuncunun bilmediği item location vermek
- world state dışında içerik uydurmak

### Çıktı formatı
Kısa kartlar:
- Current Objective
- Known Leads
- Missing Information
- Likely Next Steps
- Relevant Skills / Spells

### Soru örnekleri
- burada ne yapabilirim?
- su çipine / relic’e benzer ana hedefimiz ne?
- bu şehirde kime güvenebilirim?
- neden kapı açılmıyor olabilir?
- şu isim hakkında ne biliyoruz?

---

## 4.20 Think

### Tasarım hedefi
Ask DM dış bilgi yardımcısıysa, Think oyuncunun kendi zihinsel derlemesidir.

### Think ekranı
- Facts
- Rumors
- Hypotheses
- Open Loops
- Risks
- Resource Gaps

### Örnek davranış
Oyuncu “Think” dediğinde sistem şöyle bir sentez verir:
- Fact: kuzey kapısı mühürlü
- Fact: rahip bize üç isim verdi
- Rumor: tüccarlar geceleri kuleye kimsenin yaklaşmadığını söylüyor
- Hypothesis: kuleye giriş için ya sigil ya da içeriden izin gerekiyor
- Resource gap: lockwork düşük, dispel scroll yok
- Next step: tüccar başı veya arşiv görevlisiyle konuş

### Önemli fark
Ask DM daha yönlendirici olabilir.
Think ise daha içsel ve nötr kalmalı.

---

## 4.21 Save / Load / Settings

### Save Screen
- sol: slot listesi veya modern save cards listesi
- sağ üst: preview screenshot
- sağ alt: lokasyon, oyun süresi, zaman, party durumu, quest headline
- alt: note / custom name

### Load Screen
- save ile aynı aile
- filter: manual / auto / quick

### Settings
Sekmeler:
- Gameplay
- Combat
- Narrative
- Accessibility
- Audio
- Video
- Input

### Fallout’tan ilham alınabilecek ama özgünleştirilecek ayarlar
- non-combat difficulty
- combat difficulty
- combat speed
- combat taunts
- combat message density
- target highlight
- text delay
- running default
- audio sliders
- brightness
- mouse sensitivity
- optional: lore density / inspect verbosity / dice transparency

---

## 4.22 Elevator / Floor Selector / Portal Selector

### Amaç
Dikey veya katmanlı yerlerde basit ve hızlı geçiş.

### Ember yorumu
Aynı surface şu şeyler için kullanılabilir:
- elevator
- tower stairs selector
- ritual gate ring
- undercroft depth selector
- mine lift

### Layout
- merkezde küçük modal
- current layer display
- dikey 3–8 kat düğmesi
- kilitli katlar gri
- tehlikeli katlarda warning glyph

### Özgün varyasyonlar
- mekanik yapı → bronz düğmeler
- büyülü yapı → dönen rune halkası
- yeraltı → zincirli maden lift göstergesi

---

## 4.23 Loading Screen / Game Over / Quick Help

### Loading
- lore card
- control tip
- faction sigil
- discovered enemy silhouettes
- upcoming biome hint

### Game Over
- sadece “öldün” değil, “chronicle ended” hissi
- neden bitti?
- hangi ana hedef çöktü?
- hangi karakterler hayatta kaldı / kayboldu?
- load / restart / title seçenekleri

### Quick Help
- controls cheat sheet
- combat verbs
- trade help
- Ask About nasıl çalışır
- body armor zones açıklaması

---

# 5. MASTER PRD — CRPG SHELL AUTHORITY V1

## 5.1 Purpose
Ember RPG için tekil, diegetic, Fallout-hissine sahip ama görsel olarak özgün bir **CRPG shell authority** tanımlar.

## 5.2 In Scope
- main game shell
- bottom instrument rail
- world view + modal overlay hierarchy
- inventory
- character dossier
- codex
- map surfaces
- combat state expansion

## 5.3 Out of Scope
- backend combat math
- backend save schema
- spell resolution kernel
- dialog branching logic detayları (ayrı PRD)

## 5.4 Functional Requirements

### FR-01 Shell Layout
Gameplay screen şu zonelardan oluşur:
- World View
- Instrument Rail
- Modal Layer
- Tooltip / transient layer

### FR-02 Modal Authority
Aynı anda yalnızca bir major modal açık olabilir:
- inventory
- dossier
- codex
- map
- dialogue
- trade
- settings

### FR-03 Bottom Rail
Instrument rail şu alt-bileşenleri içerir:
- event monitor
- primary action slot
- secondary action slot
- quick spell slot
- AP/focus pips
- HP / ward / armor counters
- mode buttons

### FR-04 Context Cursor
Cursor bindirilmiş obje üzerinde default verb gösterir. Hold interaction secondary verbs listesi açar.

### FR-05 Combat Expansion
Combat başladığında rail expanded combat mode’a geçer. End turn, target zone, attack mode, cast mode görünür.

### FR-06 Keyboard Contract
- I inventory
- C dossier
- M map
- P codex
- S skills/field arts
- O settings/pause
- TAB local map / overlay
- ESC close hierarchy

### FR-07 Info Density Rule
Tüm yoğun ekranlarda minimum 3 seviye bilgi hiyerarşisi bulunmalıdır:
- primary actionable data
- secondary detail
- tertiary explanation card

### FR-08 Visual Identity Rule
Shell, Fallout’un paslı-endüstriyel trade dress’ini birebir tekrar etmemelidir. Ember shell’in malzeme dili proje çapında tek standarda bağlanır.

## 5.5 Scene Map (Godot)
```text
scenes/ui/
  crpg_shell.tscn
  instrument_rail.tscn
  event_monitor.tscn
  action_slot_widget.tscn
  status_pips_widget.tscn
  modal_host.tscn
  tooltip_card.tscn
  floor_selector_modal.tscn
```

## 5.6 State Model
```gdscript
class_name ShellState
var active_modal: String = ""
var in_combat: bool = false
var hover_entity_id: String = ""
var selected_entity_id: String = ""
var action_mode: String = "move"
var active_slots := {
    "main_hand": {},
    "off_hand": {},
    "quick_magic": {}
}
var hp: int = 0
var hp_max: int = 0
var ward: int = 0
var ward_max: int = 0
var armor_score: int = 0
var ap_current: int = 0
var ap_max: int = 0
```

## 5.7 Acceptance Criteria
- major modal açıkken ikinci major modal aynı anda overlay olmaz
- ESC önce child modalı, sonra parent modalı, en son pause menu’yü kapatır
- combat’e girince rail 200 ms içinde expanded mode’a geçer
- hover edilen obje 120 ms içinde event monitor’da adıyla görünür
- action slot icon + text + maliyet aynı frame’de güncellenir

---

# 6. MASTER PRD — DIALOGUE + ASK ABOUT + TRADE SURFACE V1

## 6.1 Purpose
Fallout 1’in en önemli hislerinden biri olan “NPC ile konuşma + keyword/topic sorma + trade” üçlüsünü Ember’e deterministik ve AI-dostu şekilde taşımak.

## 6.2 In Scope
- bark dialogue
- extended dialogue
- response list
- transcript
- ask about
- trade overlay
- disposition visibility

## 6.3 Out of Scope
- serbest generative NPC roleplay
- lore canon’ı runtime’da icat eden LLM akışı
- voice sync

## 6.4 UX Principles
1. Oyuncu bir NPC ile konuşurken aynı anda bilgi toplar, pazarlık yapar ve yeni konu açar.
2. Important NPC’ler portreli, generic NPC’ler scene-crop frame’li görünür.
3. Ask About mekanik olarak özgür, ama veri olarak deterministik olmalıdır.
4. Transcript ve topic chips birlikte çalışmalıdır.

## 6.5 Functional Requirements

### FR-01 Bark vs Extended
NPC response yalnız kısa satır ise bark gösterilir. Branch, condition, response choice veya topic support varsa extended dialogue açılır.

### FR-02 Extended Layout
Dialogue overlay şu alanları içerir:
- speaker frame
- NPC text area
- response list
- side actions: Ask About, Trade, Transcript, Leave

### FR-03 Response Metadata
Her player response şu metadata’yı taşıyabilir:
- tone_tag
- requirement
- hidden_if_unmet
- consequence_hint
- skill_used

### FR-04 Transcript
Aktif conversation session içindeki tüm satırlar transcript olarak açılabilir.

### FR-05 Ask About Input
Ask About modalı iki giriş yolu sunar:
- free text
- topic chips

### FR-06 Topic Resolution Order
Sistem topic sorgusunu şu sırayla çözmelidir:
1. exact alias match
2. canonical topic id
3. local NPC topic tags
4. quest-specific topic redirect
5. unknown fallback

### FR-07 Topic Response Types
Bir topic response şu tiplerden biri olmalıdır:
- fact
- rumor
- refusal
- redirect
- hostility trigger
- skill gate
- trust gate
- world state gate

### FR-08 Trade Transition
Trade action extended dialogue içinden açılır ve response list area’yı kaplar. Dialogue state korunur. Trade kapanınca konuşmaya geri dönülür.

### FR-09 Portraitless Dialogue
Unique portrait yoksa scene crop frame kullanılmalıdır.

### FR-10 Hidden Options
Bazı seçenekler oyuncuda görünmez; bazıları görünür ama risk taşır. Bu iki durum veri modelinde ayrı tutulur.

## 6.6 Backend Data Proposal
```python
@dataclass
class KnowledgeTopic:
    topic_id: str
    display_name: str
    aliases: list[str]
    category: str           # person / place / item / faction / event / concept
    discovered: bool = False

@dataclass
class TopicResponse:
    topic_id: str
    npc_id: str
    response_type: str      # fact / rumor / refusal / redirect / lie
    text: str
    requirement: dict | None = None
    reveals_topics: list[str] = field(default_factory=list)
    opens_dialog_state: str | None = None
    affects_disposition: int = 0

@dataclass
class ConversationSession:
    npc_id: str
    dialog_id: str
    transcript: list[dict]
    discovered_topics: list[str]
    current_state_id: str
    can_trade: bool = False
```

## 6.7 Godot Scene Map
```text
scenes/ui/dialogue/
  bark_bubble.tscn
  dialogue_overlay.tscn
  speaker_frame.tscn
  response_list.tscn
  topic_probe_modal.tscn
  transcript_modal.tscn
  trade_overlay.tscn
```

## 6.8 Acceptance Criteria
- generic NPC ile konuşurken portrait yoksa framed scene-crop görünür
- topic alias match doğru canonical topic’e çözülür
- bilinmeyen topic fallback response üretir ama state bozmaz
- trade’e girip çıkınca conversation node aynı bağlamda devam eder
- transcript kapanınca cevap listesi aynı scroll konumunda geri gelir

---

# 7. MASTER PRD — ASK DM + THINK V1

## 7.1 Purpose
Pause menu içinden, oyuncuya keşfedilmiş bilgiye dayalı rehberlik ve düşünce örgüleme sunmak.

## 7.2 Design Constraint
Bu sistem **hakikat üreten narrator AI** değildir.
Bu sistem **knowledge graph summarizer + deterministic hint layer**’dır.

## 7.3 In Scope
- Ask DM surface
- Think surface
- question classification
- grounded answer cards
- known facts / rumors / blockers synthesis

## 7.4 Out of Scope
- GM fiat
- hidden content reveal
- future prediction without evidence
- dynamic canon creation

## 7.5 Functional Requirements

### FR-01 Safe Access Rule
Ask DM / Think yalnız güvenli anlarda tam ekran açılır. Combat içinde mini version veya disabled state kullanılır.

### FR-02 Ask DM Input
Oyuncu serbest soru sorabilir veya hazır prompt seçebilir:
- burada ne yapabilirim?
- kimi sorgulamalıyım?
- bu görevde ne eksik?
- X hakkında ne biliyoruz?

### FR-03 Intent Classification
Sistem soruyu şu intent’lerden birine sınıflar:
- next_step
- entity_summary
- location_guidance
- blocker_analysis
- objective_status
- resource_gap

### FR-04 Grounding Sources
Ask DM yalnız şunları kullanır:
- active quests
- discovered topics
- transcript pins
- visible interactables
- known NPC relations
- explored maps
- current inventory / spell loadout
- failed checks history (isteğe bağlı)

### FR-05 Answer Card Format
Cevaplar tek parça düz metin yerine card set olarak verilir:
- What You Know
- What You Don’t Know
- Likely Next Moves
- Useful Tools / Skills
- Risks

### FR-06 Think Output
Think oyuncu zihni gibi davranır ve şu blokları üretir:
- Facts
- Rumors
- Hypotheses
- Open Threads
- Immediate Plan

### FR-07 Speculation Flag
Her Think maddesi `certainty` taşır:
- confirmed
- likely
- uncertain
- rumor

### FR-08 No Spoiler Rule
Undiscovered location, hidden switch, unrevealed betrayal, future scripted event asla doğrulanmaz.

## 7.6 Backend Data Proposal
```python
@dataclass
class KnownFact:
    fact_id: str
    text: str
    source_type: str        # dialogue / inspect / map / quest / battle / book
    topic_ids: list[str]
    certainty: str          # confirmed / likely / rumor
    region_id: str = ""
    npc_id: str = ""

@dataclass
class InsightAnswer:
    intent: str
    cards: list[dict]       # {title, bullets, certainty}

@dataclass
class ReflectionBundle:
    facts: list[KnownFact]
    rumors: list[KnownFact]
    hypotheses: list[str]
    blockers: list[str]
    next_steps: list[str]
```

## 7.7 Godot Scene Map
```text
scenes/ui/pause/
  pause_menu.tscn
  ask_dm_panel.tscn
  think_panel.tscn
  insight_card.tscn
  question_chip_row.tscn
```

## 7.8 Acceptance Criteria
- Ask DM, keşfedilmemiş bir odayı varmış gibi anlatmaz
- Think, confirmed ve rumor bilgiyi ayrı gruplar
- aynı soru iki kez sorulduğunda aynı knowledge state içinde aynı grounded core answer gelir
- oyuncu inventory’sinde kilit açma aracı yoksa blocker analysis bunu yakalar

---

# 8. MASTER PRD — MAPS + TRAVEL + REST V1

## 8.1 Purpose
Keşif, seyahat, yerel harita ve zaman atlatma yüzeylerini tek aile altında toplamak.

## 8.2 Functional Requirements
- local map current floor’u gösterir
- full codex map listesi discovered sites içerir
- world map fog-of-war taşır
- bilinen lokasyon listesi hızlı seyahati destekler
- seyahat path’i ETA ve risk üretir
- rest seçenekleri healing projection üretir
- random encounter world travel’ı kesebilir

## 8.3 Data Proposal
```python
@dataclass
class WorldSite:
    site_id: str
    name: str
    discovered: bool
    visited: bool
    region_type: str
    travel_risk: float

@dataclass
class LocalMapFloor:
    area_id: str
    floor_index: int
    discovered_cells: list[tuple[int, int]]
    points_of_interest: list[str]

@dataclass
class RestOption:
    label: str
    duration_minutes: int | None
    until_phase: str = ""
```

## 8.4 Acceptance Criteria
- unexplored world regions tam görünmez değil, silhouette seviyesinde kalır
- discovered site listesi yalnız gerçekten bilinen yerleri gösterir
- rest unsafe area’da ambush warning verir
- local map floor selector katlar arasında state kaybetmez

---

# 9. Godot implementation için build order

## Phase 1 — Shell temel iskelet
1. `crpg_shell.tscn`
2. `instrument_rail.tscn`
3. `modal_host.tscn`
4. hover monitor + status counters

## Phase 2 — Dossier + Inventory
5. unified dossier scene
6. equipment slots
7. inventory list + item details
8. corpse/container modal

## Phase 3 — Dialogue family
9. bark bubble
10. dialogue overlay
11. transcript modal
12. trade overlay
13. ask about modal

## Phase 4 — Codex + Maps
14. codex root scene
15. quest/status tabs
16. local map
17. world map
18. rest screen

## Phase 5 — Pause intelligence
19. pause menu
20. ask dm panel
21. think panel
22. knowledge card widgets

## Phase 6 — Combat overlay
23. AP/focus expansion
24. target zone selector
25. combat log density controls
26. spell targeting surface

---

# 10. AI codegen prompt paketi

## Prompt 1 — Shell
"Create a Godot 4.6 `Control` scene named `crpg_shell.tscn` for an isometric CRPG. The top 75% is world viewport. The bottom 25% is a diegetic instrument rail with: event monitor on left, three active slots in center, AP/Focus pips above, HP/Ward/Armor counters on right, and modal host above the rail. Only one major modal may be open at a time. Provide GDScript for modal open/close hierarchy and keyboard shortcuts. Do not use Fallout names or art direction; use ember-bronze rune-tech styling." 

## Prompt 2 — Dialogue Overlay
"Create a Godot 4.6 conversation overlay for a CRPG with two modes: portrait dialogue and portraitless scene-crop dialogue. Layout: speaker frame, NPC text, response list, side actions (Ask About, Trade, Transcript, Leave). Responses can carry metadata tags like Threaten, Charm, Lore, Arcana. Include keyboard navigation and callbacks for opening trade and ask-about modals." 

## Prompt 3 — Ask About
"Implement a deterministic topic-query modal for Godot 4.6 called `topic_probe_modal.tscn`. It contains a text field, discovered topic chips, submit button, cancel button, and response preview area. It should resolve free text against canonical topics and aliases, then emit `topic_submitted(topic_text)` to the game session." 

## Prompt 4 — Ask DM / Think
"Build a pause-menu intelligence surface for a deterministic CRPG. Add `Ask DM` and `Think` tabs. Ask DM returns grounded answer cards using only discovered facts, active objectives, visible interactables, known NPC relations, and current inventory. Think groups information into Facts, Rumors, Hypotheses, Open Threads, and Immediate Plan. The UI must visually separate certainty levels and must not imply hidden knowledge." 

## Prompt 5 — Unified Dossier
"Build a Godot 4.6 character dossier scene reused for both character creation and in-game character sheet. Left column attributes, middle paper doll with full body armor slots plus magic attunement slots, right column skills/spells, bottom explanation card. Include mode switching between creation mode and runtime mode." 

---

# 11. Son karar tavsiyesi

Eğer bir tek şeyi Fallout 1’den gerçekten taşıyacaksan, bu şu üçlü olsun:
1. **alt komut rayı + üst dünya görünümü**
2. **portreli diyalog + Ask About**
3. **karanlıktan açılan dünya haritası + zaman baskısı hissi**

Ve eğer bir tek şeyi kesinlikle birebir taşımayacaksan, bu şu olsun:
1. exact metal frame look
2. exact CRT green + mascot + button wording
3. birebir Pip-Boy / Skilldex / Tell Me About adları ve yüzey formu

Bu belgeyi repo içindeki mevcut PRD’lerin üzerine bir `surface authority overlay` olarak düşünebilirsin.
