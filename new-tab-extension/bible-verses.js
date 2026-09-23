// ==========================================================
// BIBLICKÉ VERŠE - S predpripravenými textami pre rýchle zobrazenie
// ==========================================================

// Biblické verše s textami
const bibleVersesWithText = [
    {
        ref: "Ján 3,16",
        text: "Veď Boh tak miloval svet, že dal svojho jednorodeného Syna, aby nezahynul nik, kto v neho verí, ale aby mal večný život."
    },
    {
        ref: "Matúš 22,37",
        text: "On mu povedal: \"Milovať budeš Pána, svojho Boha, celým svojím srdcom, celou svojou dušou a celou svojou mysľou!"
    },
    {
        ref: "Matúš 22,39",
        text: "Druhé je mu podobné: Milovať budeš svojho blížneho ako seba samého!"
    },
    {
        ref: "Galaťanom 5,13",
        text: "Lebo vy ste povolaní pre slobodu, bratia, len nedávajte slobodu za príležitosť telu, ale navzájom si slúžte v láske!"
    },
    {
        ref: "Ján 13,34",
        text: "Nové prikázanie vám dávam, aby ste sa milovali navzájom. Aby ste sa aj vy vzájomne milovali, ako som ja miloval vás."
    },
    {
        ref: "Ján 15,13",
        text: "Nik nemá väčšiu lásku ako ten, kto položí svoj život za svojich priateľov."
    },
    {
        ref: "Rimanom 5,8",
        text: "Ale Boh dokazuje svoju lásku k nám tým, že Kristus zomrel za nás, keď sme boli ešte hriešnici."
    },
    {
        ref: "Efezanom 5,1-2",
        text: "Napodobňujte Boha ako milované deti a žite v láske tak, ako aj Kristus miluje nás a vydal seba samého Bohu za nás ako dar a obetu ľúbeznej vône!"
    },
    {
        ref: "Hebrejom 10,23",
        text: "Neochvejne sa držme nádeje, ktorú vyznávame, lebo verný je ten, ktorý dal prisľúbenie."
    },
    {
        ref: "1 Korinťanom 15,58",
        text: "Buďte pevní, neochvejní, vždy plní horlivosti pre Pánovo dielo."
    },
    {
        ref: "Jeremiáš 17,7",
        text: "Požehnaný je muž, ktorý dôveruje v Pána, Pán bude jeho nádejou."
    },
    {
        ref: "Žalm 37,3",
        text: "Ale spoľahni sa na Pána a dobre rob a budeš bývať v svojej krajine a tešiť sa z bezpečia."
    },
    {
        ref: "Jeremiáš 29,11",
        text: "Veď ja poznám zámer, ktorý mám s vami – hovorí Pán. Sú to myšlienky pokoja a nie súženia: dám vám budúcnosť a nádej."
    },
    {
        ref: "Ján 14,1",
        text: "Nech sa vám srdce nevzrušuje! Veríte v Boha, verte aj vo mňa."
    },
    {
        ref: "Habakuk 2,4",
        text: "Hľa, nadúva sa, v kom nie je duša priama, spravodlivý však bude žiť pre svoju vernosť.\""
    },
    {
        ref: "Rimanom 5,5",
        text: "A nádej nezahanbuje, lebo Božia láska je rozliata v našich srdciach skrze Ducha Svätého, ktorého sme dostali."
    },
    {
        ref: "Rimanom 15,13",
        text: "Boh nádeje nech vás naplní všetkou radosťou a pokojom vo viere, aby ste v sile Ducha Svätého oplývali nádejou."
    },
    {
        ref: "Filipanom 4,13",
        text: "Všetko môžem v tom, ktorý ma posilňuje."
    },
    {
        ref: "Izaiáš 41,10",
        text: "Neboj sa, veď som s tebou ja, neobzeraj sa, veď ja som tvoj Boh, posilňujem ťa, ba pomáham ti, držím ťa svojou spásnou pravicou."
    },
    {
        ref: "Jozue 1,9",
        text: "Či som ti neprikázal: Buď silný a udatný, neboj sa a neľakaj sa!? Veď Pán, tvoj Boh, je s tebou pri všetkom, čo podnikneš!\""
    },
    {
        ref: "Žalm 27,1",
        text: "Dávidov žalm. Pán je moje svetlo a moja spása, koho sa mám báť? Pán je ochranca môjho života, pred kým sa mám strachovať?"
    },
    {
        ref: "Lukáš 2,10",
        text: "ale anjel im povedal: \"Nebojte sa. Zvestujem vám veľkú radosť, ktorá bude patriť všetkým ľuďom:"
    },
    {
        ref: "Matúš 10,28",
        text: "Nebojte sa tých, čo zabíjajú telo, ale dušu zabiť nemôžu. Skôr sa bojte toho, ktorý môže i dušu, i telo zahubiť v pekle."
    },
    {
        ref: "Lukáš 1,37",
        text: "Lebo Bohu nič nie je nemožné.\""
    },
    {
        ref: "Žalm 18,3",
        text: "Pane, opora moja, útočište moje, osloboditeľ môj. Bože môj, moja pomoc, tebe dôverujem; ty si môj štít, sila mojej spásy a môj ochranca."
    },
    {
        ref: "Efezanom 6,10",
        text: "Napokon upevňujte sa v Pánovi a v sile jeho moci."
    },
    {
        ref: "Ján 4,34",
        text: "Ježiš im povedal: \"Mojím pokrmom je plniť vôľu toho, ktorý ma poslal, a dokonať jeho dielo."
    },
    {
        ref: "Ján 14,27",
        text: "Pokoj vám zanechávam, svoj pokoj vám dávam. Ale ja vám nedávam, ako svet dáva. Nech sa vám srdce nevzrušuje a nestrachuje."
    },
    {
        ref: "Matúš 11,28",
        text: "Poďte ku mne všetci, ktorí sa namáhate a ste preťažení, a ja vás posilním."
    },
    {
        ref: "Žalm 23,1",
        text: "Dávidov žalm. Pán je môj pastier, nič mi nechýba:"
    },
    {
        ref: "Matúš 5,4",
        text: "Blahoslavení plačúci, lebo oni budú potešení."
    },
    {
        ref: "Žalm 147,3",
        text: "Uzdravuje skľúčených srdcom a obviazuje ich rany."
    },
    {
        ref: "Lukáš 2,14",
        text: "\"Sláva Bohu na výsostiach a na zemi pokoj ľuďom dobrej vôle.\""
    },
    {
        ref: "Filipanom 4,7",
        text: "A Boží pokoj, ktorý prevyšuje každú chápavosť, uchráni vaše srdcia a vaše mysle v Kristovi Ježišovi."
    },
    {
        ref: "Matúš 11,29",
        text: "Vezmite na seba moje jarmo a učte sa odo mňa, lebo som tichý a pokorný srdcom; a nájdete odpočinok pre svoju dušu."
    },
    {
        ref: "Filipanom 4,4",
        text: "Ustavične sa radujte v Pánovi! Opakujem: Radujte sa!"
    },
    {
        ref: "Žalm 118,24",
        text: "Toto je deň, ktorý urobil Pán, plesajme a radujme sa z neho."
    },
    {
        ref: "Rimanom 12,15",
        text: "Radujte sa s radujúcimi, plačte s plačúcimi!"
    },
    {
        ref: "Matúš 5,12",
        text: "radujte sa a jasajte, lebo máte hojnú odmenu v nebi. Tak prenasledovali aj prorokov, ktorí boli pred vami."
    },
    {
        ref: "Galaťanom 5,22-23",
        text: "Ale ovocie Ducha je láska, radosť, pokoj, zhovievavosť, láskavosť, dobrota, vernosť, miernosť, zdržanlivosť. Proti tomuto zákona niet."
    },
    {
        ref: "Lukáš 10,20",
        text: "No neradujte sa z toho, že sa vám poddávajú duchovia, ale radujte sa, že sú vaše mená zapísané v nebi.\""
    },
    {
        ref: "Žalm 136,1",
        text: "Oslavujte Pána, lebo je dobrý, lebo jeho milosrdenstvo je večné."
    },
    {
        ref: "Žalm 100,4",
        text: "Vstupujte do jeho brán s piesňou chvály a do jeho nádvorí s piesňami oslavnými; chváľte ho a velebte jeho meno."
    },
    {
        ref: "Efezanom 5,20",
        text: "Ustavične vzdávajte vďaky za všetko Bohu a Otcovi v mene nášho Pána Ježiša Krista"
    },
    {
        ref: "Matúš 7,7",
        text: "Proste a dostanete! Hľadajte a nájdete! Klopte a otvoria vám!"
    },
    {
        ref: "Matúš 21,22",
        text: "A dostanete všetko, o čo budete s vierou prosiť v modlitbe.–"
    },
    {
        ref: "Matúš 26,41",
        text: "Bdejte a modlite sa, aby ste neprišli do pokušenia! Duch je síce ochotný, ale telo slabé.\""
    },
    {
        ref: "Matúš 6,5",
        text: "A keď sa modlíte, nebuďte ako pokrytci, ktorí sa radi postojačky modlievajú v synagógach a na rohoch ulíc, aby ich ľudia videli. Veru, hovorím vám: Už dostali svoju odmenu."
    },
    {
        ref: "Matúš 6,6",
        text: "Ale keď sa ty ideš modliť, vojdi do svojej izby, zatvor za sebou dvere a modli sa k svojmu Otcovi, ktorý je v skrytosti. A tvoj Otec ťa odmení, lebo on vidí aj v skrytosti."
    },
    {
        ref: "Lukáš 6,37",
        text: "Nesúďte a nebudete súdení. Neodsudzujte a nebudete odsúdení! Odpúšťajte a odpustí sa vám."
    },
    {
        ref: "Izaiáš 1,18",
        text: "Poďte, pravôťme sa! – hovorí Pán. Ak budú vaše hriechy sťa šarlát, budú obielené ako sneh, ak sa budú červenať sťa purpur, budú ako vlna (biele)."
    },
    {
        ref: "Matúš 6,14",
        text: "Lebo ak vy odpustíte ľuďom ich poklesky, aj váš nebeský Otec vám odpustí."
    },
    {
        ref: "Matúš 9,2",
        text: "Tu mu priniesli ochrnutého človeka, ktorý ležal na lôžku. Keď Ježiš videl ich vieru, povedal ochrnutému: \"Dúfaj, synu, odpúšťajú sa ti hriechy.\""
    },
    {
        ref: "Matúš 18,21-22",
        text: "Vtedy k nemu pristúpil Peter a povedal mu: \"Pane, koľko ráz mám odpustiť svojmu bratovi, keď sa proti mne prehreší? Azda sedem ráz?\" Ježiš mu odpovedal: \"Hovorím ti: Nie sedem ráz, ale sedemdesiatsedem ráz."
    },
    {
        ref: "Matúš 5,7",
        text: "Blahoslavení milosrdní, lebo oni dosiahnu milosrdenstvo."
    },
    {
        ref: "Lukáš 6,36",
        text: "Buďte milosrdní, ako je milosrdný váš Otec!"
    },
    {
        ref: "Žalm 146,9",
        text: "Pán ochraňuje cudzincov, ujíma sa siroty a vdovy, ale hatí cesty hriešnikov."
    },
    {
        ref: "Matúš 5,6",
        text: "Blahoslavení lační a smädní po spravodlivosti, lebo oni budú nasýtení."
    },
    {
        ref: "Matúš 5,5",
        text: "Blahoslavení tichí, lebo oni budú dedičmi zeme."
    },
    {
        ref: "Žalm 111,10",
        text: "bohabojnosť je počiatok múdrosti a múdro robia všetci, čo ju pestujú; jeho chvála ostáva naveky."
    },
    {
        ref: "Jakub 1,5",
        text: "Ak niekomu z vás chýba múdrosť, nech si prosí od Boha, ktorý dáva všetkým štedro a bez výčitky, a dostane ju."
    },
    {
        ref: "Ján 14,6",
        text: "Ježiš mu odpovedal: \"Ja som cesta, pravda a život. Nik nepríde k Otcovi, iba cezo mňa."
    },
    {
        ref: "Ján 8,32",
        text: "poznáte pravdu a pravda vás vyslobodí.\""
    },
    {
        ref: "Žalm 119,105",
        text: "Tvoje slovo je svetlo pre moje nohy a pochodeň na mojich chodnících."
    },
    {
        ref: "Matúš 5,13",
        text: "Vy ste soľ zeme. Ak soľ stratí chuť, čím ju osolia? Už nie je na nič, len ju vyhodiť von, aby ju ľudia pošliapali."
    },
    {
        ref: "Matúš 5,16",
        text: "Nech tak svieti vaše svetlo pred ľuďmi, aby videli vaše dobré skutky a oslavovali vášho Otca, ktorý je na nebesiach."
    },
    {
        ref: "Ján 8,12",
        text: "A Ježiš im zasa povedal: \"Ja som svetlo sveta. Kto mňa nasleduje, nebude chodiť vo tmách, ale bude mať svetlo života.\""
    },
    {
        ref: "Matúš 5,8",
        text: "Blahoslavení čistého srdca, lebo oni uvidia Boha."
    },
    {
        ref: "Ján 6,35",
        text: "Ježiš im povedal: \"Ja som chlieb života. Kto prichádza ku mne, nikdy nebude hladovať, a kto verí vo mňa, nikdy nebude žízniť."
    },
    {
        ref: "Ján 10,11",
        text: "Ja som dobrý pastier. Dobrý pastier položí svoj život za ovce."
    },
    {
        ref: "Ján 11,25",
        text: "Ježiš jej povedal: \"Ja som vzkriesenie a život. Kto verí vo mňa, bude žiť, aj keď umrie."
    },
    {
        ref: "Ján 15,5",
        text: "Ja som vinič, vy ste ratolesti. Kto ostáva vo mne a ja v ňom, prináša veľa ovocia; lebo bezo mňa nemôžete nič urobiť."
    },
    {
        ref: "Ján 15,1",
        text: "Ja som pravý vinič a môj Otec je vinohradník."
    },
    {
        ref: "Hebrejom 13,8",
        text: "Ježiš Kristus je ten istý včera i dnes a naveky!"
    },
    {
        ref: "Ján 3,17",
        text: "Lebo Boh neposlal Syna na svet, aby svet odsúdil, ale aby sa skrze neho svet spasil."
    },
    {
        ref: "Ján 14,9",
        text: "Ježiš mu vravel: \"Filip, toľký čas som s vami a nepoznáš ma?! Kto vidí mňa, vidí Otca. Ako môžeš hovoriť: „Ukáž nám Otca?!–"
    },
    {
        ref: "Efezanom 2,8",
        text: "Lebo spasení ste milosťou skrze vieru; a to nie je z vás, je to Boží dar:"
    },
    {
        ref: "Rimanom 6,23",
        text: "Lebo mzdou hriechu je smrť, ale Boží dar je večný život v Kristovi Ježišovi, našom Pánovi."
    },
    {
        ref: "Efezanom 2,10",
        text: "Veď sme jeho dielo, stvorení v Kristovi Ježišovi pre dobré skutky, ktoré pripravil Boh, aby sme ich konali."
    },
    {
        ref: "Ján 1,16",
        text: "Z jeho plnosti sme my všetci dostali milosť za milosťou."
    },
    {
        ref: "Galaťanom 3,28",
        text: "Už niet Žida ani Gréka, niet otroka ani slobodného, niet muža a ženy, lebo vy všetci ste jeden v Kristovi Ježišovi."
    },
    {
        ref: "Ján 17,3",
        text: "A večný život je v tom, aby poznali teba, jediného pravého Boha, a toho, ktorého si poslal, Ježiša Krista."
    },
    {
        ref: "Ján 14,15",
        text: "Ak ma milujete, budete zachovávať moje prikázania."
    },
    {
        ref: "Kolosanom 3,23",
        text: "Čokoľvek robíte, robte z tej duše ako Pánovi, a nie ako ľuďom!"
    },
    {
        ref: "Matúš 5,48",
        text: "Vy teda buďte dokonalí, ako je dokonalý váš nebeský Otec."
    },
    {
        ref: "Matúš 23,12",
        text: "Kto sa povyšuje, bude ponížený, a kto sa ponižuje, bude povýšený."
    },
    {
        ref: "Matúš 24,35",
        text: "Nebo a zem sa pominú, ale moje slová sa nepominú."
    },
    {
        ref: "Hebrejom 4,12",
        text: "Lebo živé je Božie slovo, účinné a ostrejšie ako každý dvojsečný meč; preniká až po oddelenie duše od ducha a kĺbov od špiku a rozsudzuje myšlienky a úmysly srdca."
    },
    {
        ref: "Matúš 4,4",
        text: "On odvetil: \"Napísané je: „Nielen z chleba žije človek, ale z každého slova, ktoré vychádza z Božích úst.\"\""
    },
    {
        ref: "Ján 6,63",
        text: "Duch oživuje, telo nič neosoží. Slová, ktoré som vám povedal, sú Duch a život."
    },
    {
        ref: "Matúš 18,20",
        text: "Lebo kde sú dvaja alebo traja zhromaždení v mojom mene, tam som ja medzi nimi.\""
    },
    {
        ref: "Filipanom 2,5",
        text: "Zmýšľajte tak ako Kristus Ježiš:"
    },
    {
        ref: "Efezanom 4,5",
        text: "Jeden je Pán, jedna viera, jeden krst."
    },
    {
        ref: "Jakub 1,12",
        text: "Blahoslavený muž, ktorý vydrží skúšku, lebo keď sa osvedčí, dostane veniec života, ktorý Boh prisľúbil tým, čo ho milujú."
    },
    {
        ref: "Matúš 24,13",
        text: "Ale kto vytrváleho konca, bude spasený."
    },
    {
        ref: "Lukáš 21,19",
        text: "Ak vytrváte, zachováte si život."
    },
    {
        ref: "Lukáš 6,38",
        text: "Dávajte a dajú vám: mieru dobrú, natlačenú, natrassenú, vrchovatú vám dajú do lona. Lebo akou mierou budete merať vy, takou sa nameria aj vám.\""
    },
    {
        ref: "Galaťanom 6,7",
        text: "Nemýľte sa: Boh sa vysmievať nedá. Čo človek zaseje, to bude aj žať."
    },
    {
        ref: "Galaťanom 6,9",
        text: "Neúnavne konajme dobro, lebo ak neochabneme, budeme v pravom čase žať."
    },
    {
        ref: "Matúš 5,10",
        text: "Blahoslavení prenasledovaní pre spravodlivosť, lebo ich je nebeské kráľovstvo."
    },
    {
        ref: "Matúš 6,33",
        text: "Hľadajte teda najprv Božie kráľovstvo a jeho spravodlivosť a toto všetko dostanete navyše."
    },
    {
        ref: "Matúš 6,21",
        text: "Lebo kde je tvoj poklad, tam bude aj tvoje srdce."
    },
    {
        ref: "Matúš 6,19",
        text: "Nezhromažďujte si poklady na zemi, kde ich moľ a hrdza ničia a kde sa zlodeji dobýjajú a kradnú."
    },
    {
        ref: "Matúš 6,20",
        text: "V nebi si zhromažďujte poklady; tam ich ničí ani moľ, ani hrdza a tam sa zlodeji nedobýjajú a nekradnú."
    },
    {
        ref: "Matúš 16,26",
        text: "Veď čo osožíveka keby aj celý svet získal, a svojej duši by uškodil?! Alebo za čo vymení človek svoju dušu?!"
    },
    {
        ref: "Matúš 28,20",
        text: "a naučte ich zachovávať všetko, čo som vám prikázal. A hľa, ja som s vami po všetky dni až do skončenia sveta.\""
    },
    {
        ref: "Matúš 6,26",
        text: "Pozrite sa na nebeské vtáky: nesejú, ani nežnú, ani do stodôl nezhromažďujú, a váš nebeský Otec ich živí. Nie ste vy oveľa viac ako ony?"
    },
    {
        ref: "Zjavenie 3,20",
        text: "Hľa, stojím pri dverách a klopem. Kto počúvne môj hlas a otvorí dvere, k tomu vojdem a budem s ním večerať a on so mnou."
    },
    {
        ref: "Ján 3,3",
        text: "Ježiš mu odpovedal: \"Veru, veru, hovorím ti: Ak sa niekto nenarodí zhora, nemôže uzrieť Božie kráľovstvo.\""
    },
    {
        ref: "Ján 3,6",
        text: "Čo sa narodilo z tela, je telo, a čo sa narodilo z Ducha, je duch."
    },
    {
        ref: "Ján 4,24",
        text: "Boh je duch a tí, čo sa mu klaňajú, musia sa mu klaňať v Duchu a pravde.\""
    },
    {
        ref: "Matúš 6,10",
        text: "príď tvoje kráľovstvo, buď tvoja vôľa, ako v nebi, tak i na zemi."
    },
    {
        ref: "Matúš 26,39",
        text: "Trochu poodišiel, padol na tvár a modlil sa: \"Otče môj, ak je možné, nech ma minie tento kalich. No nie ako ja chcem, ale ako ty.\""
    },
    {
        ref: "Matúš 12,50",
        text: "Lebo každý, kto plní vôľu môjho Otca, ktorý je na nebesiach, je môj brat i sestra i matka.\""
    },
    {
        ref: "Izaiáš 65,17",
        text: "Lebo hľa, ja stvorím nové nebo a novú zem a na predošlé sa nebude spomínať, ani na myseľ neprídu,"
    },
    {
        ref: "Zjavenie 21,1",
        text: "Videl som nové nebo a novú zem, lebo prvé nebo a prvá zem sa pominuli a ani mora už niet."
    },
    {
        ref: "Lukáš 12,32",
        text: "Neboj sa, maličké stádo, lebo vášmu Otcovi sa zapáčilo dať vám kráľovstvo."
    },
    {
        ref: "Ján 14,2",
        text: "V dome môjho Otca je mnoho príbytkov. Keby to tak nebolo, bol by som vám povedal, že vám idem pripraviť miesto?!"
    },
    {
        ref: "Zjavenie 22,12",
        text: "Hľa, prídem čoskoro a moja odplata so mnou; odmením každého podľa jeho skutkov."
    },
    {
        ref: "Zjavenie 22,20",
        text: "Ten, čo to dosvedčuje, hovorí: \"Áno, prídem čoskoro.\" \"Amen. Príď, Pane Ježišu!\""
    },
    {
        ref: "Matúš 18,19",
        text: "A zasa vám hovorím: Ak budú dvaja z vás na zemi jednomyseľne prosiť o čokoľvek, dostanú to od môjho Otca, ktorý je na nebesiach."
    },
    {
        ref: "Lukáš 17,6",
        text: "Pán vravel: \"Keby ste mali vieru ako horčičné zrnko a povedali by ste tejto moruši: „Vytrhni sa aj s koreňom a presaď sa do mora,– poslúchla by vás."
    }
];
       