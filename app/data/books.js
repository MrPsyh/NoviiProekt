// Сборник книг. Каждая книга: уровень (A1–C1), premium (нужна подписка или промокод),
// главы с абзацами. Чтобы добавить книгу — допишите объект в массив BOOKS.
// Тексты A1–B2 написаны специально для приложения, «Sterntaler» (Гримм) и
// «Die Verwandlung» (Кафка, отрывок) — общественное достояние.

export const BOOKS = [
  {
    id: 'anna-berlin',
    title: 'Anna in Berlin',
    author: 'Lesefreund',
    level: 'A1',
    premium: false,
    color: '#f4a261',
    emoji: '🏙️',
    description: {
      ru: 'Анна впервые приезжает в Берлин. Очень простые предложения.',
      en: 'Anna visits Berlin for the first time. Very simple sentences.',
    },
    chapters: [
      {
        title: 'Kapitel 1: Der Zug',
        paragraphs: [
          'Anna ist zwanzig Jahre alt. Sie kommt aus Polen. Heute fährt sie mit dem Zug nach Berlin.',
          'Der Zug ist groß und schnell. Anna sitzt am Fenster. Sie trinkt Kaffee und isst einen Apfel.',
          'Neben Anna sitzt ein Mann. Er liest eine Zeitung. „Hallo“, sagt der Mann. „Wohin fahren Sie?“',
          '„Ich fahre nach Berlin“, sagt Anna. „Ich lerne dort Deutsch.“ Der Mann lächelt. „Berlin ist sehr schön“, sagt er.',
        ],
      },
      {
        title: 'Kapitel 2: Die Stadt',
        paragraphs: [
          'Der Zug ist jetzt in Berlin. Anna nimmt ihren Koffer. Der Bahnhof ist sehr groß. Hier sind viele Menschen.',
          'Anna sucht den Bus. Sie fragt eine Frau: „Entschuldigung, wo ist der Bus Nummer hundert?“ Die Frau sagt: „Der Bus ist dort, links.“',
          'Anna fährt mit dem Bus durch die Stadt. Sie sieht das Brandenburger Tor, einen Park und viele Cafés.',
          'Am Abend ist Anna müde, aber glücklich. Sie schreibt ihrer Mutter: „Berlin ist toll! Morgen beginnt mein Deutschkurs.“',
        ],
      },
    ],
  },
  {
    id: 'hund-max',
    title: 'Der kleine Hund Max',
    author: 'Lesefreund',
    level: 'A1',
    premium: false,
    color: '#8ecae6',
    emoji: '🐶',
    description: {
      ru: 'Маленький пёс Макс теряется в парке. История для самых начинающих.',
      en: 'Max, a little dog, gets lost in the park. A story for absolute beginners.',
    },
    chapters: [
      {
        title: 'Max ist weg',
        paragraphs: [
          'Max ist ein kleiner Hund. Er ist braun und weiß. Max wohnt mit Familie Müller in einem Haus.',
          'Jeden Morgen geht Tom mit Max in den Park. Tom ist zehn Jahre alt. Max liebt den Park. Dort spielt er mit einem roten Ball.',
          'Heute wirft Tom den Ball sehr weit. Max läuft und läuft. Dann ist Max weg! Tom ruft: „Max! Max! Wo bist du?“',
          'Tom sucht überall. Er sucht hinter den Bäumen und neben dem See. Aber Max ist nicht da. Tom ist sehr traurig.',
          'Plötzlich hört Tom etwas. „Wau! Wau!“ Max sitzt bei einer alten Frau auf der Bank. Sie gibt ihm ein Stück Brot.',
          '„Ist das dein Hund?“, fragt die Frau. „Ja!“, sagt Tom. „Danke!“ Tom und Max gehen zusammen nach Hause. Max ist müde, aber er hat den Ball im Mund.',
        ],
      },
    ],
  },
  {
    id: 'tag-am-meer',
    title: 'Ein Tag am Meer',
    author: 'Lesefreund',
    level: 'A2',
    premium: false,
    color: '#2a9d8f',
    emoji: '🌊',
    description: {
      ru: 'Семья проводит день на Северном море. Прошедшее время Perfekt.',
      en: 'A family spends a day at the North Sea. Practises the Perfekt tense.',
    },
    chapters: [
      {
        title: 'Die Reise',
        paragraphs: [
          'Am Samstag ist Familie Schneider früh aufgestanden. Das Wetter war perfekt: Die Sonne hat geschienen und es war warm.',
          'Papa hat das Auto gepackt. Mama hat Brötchen, Käse und Obst mitgenommen. Die Kinder, Lena und Paul, haben ihre Badesachen gesucht.',
          'Die Fahrt hat zwei Stunden gedauert. Unterwegs haben sie Musik gehört und gesungen. Paul hat die ganze Zeit gefragt: „Sind wir bald da?“',
        ],
      },
      {
        title: 'Am Strand',
        paragraphs: [
          'Endlich haben sie das Meer gesehen. Das Wasser war blau und der Sand war weich. Lena ist sofort ins Wasser gelaufen, aber das Wasser war ziemlich kalt!',
          'Paul hat eine große Sandburg gebaut. Papa hat ihm geholfen. Mama hat ein Buch gelesen und ist kurz eingeschlafen.',
          'Am Nachmittag sind sie in ein kleines Restaurant gegangen und haben Fisch gegessen. Danach hat jeder ein Eis bekommen.',
          'Am Abend sind alle müde nach Hause gefahren. Im Auto hat Paul gesagt: „Das war der beste Tag in diesem Sommer!“',
        ],
      },
    ],
  },
  {
    id: 'haus-am-see',
    title: 'Das alte Haus am See',
    author: 'Lesefreund',
    level: 'B1',
    premium: true,
    color: '#6d597a',
    emoji: '🏚️',
    description: {
      ru: 'Небольшая загадочная история о старом доме и забытом письме. Präteritum, придаточные.',
      en: 'A small mystery about an old house and a forgotten letter. Präteritum, subordinate clauses.',
    },
    chapters: [
      {
        title: 'Das Erbe',
        paragraphs: [
          'Als Jonas den Brief vom Notar öffnete, konnte er kaum glauben, was er las: Seine Großtante Hilde, die er nur zweimal in seinem Leben gesehen hatte, hatte ihm ein Haus vererbt.',
          'Das Haus lag an einem kleinen See in Brandenburg, weit weg von der nächsten Stadt. Jonas, der in einer winzigen Wohnung in Hamburg wohnte, beschloss, es sich am Wochenende anzusehen.',
          'Schon von Weitem sah er, dass das Haus seit Jahren leer stand. Das Dach war mit Moos bedeckt, und im Garten wuchsen die Brennnesseln fast bis zu den Fenstern.',
        ],
      },
      {
        title: 'Das Geheimnis',
        paragraphs: [
          'Drinnen roch es nach Staub und alten Büchern. Die Möbel waren mit weißen Tüchern bedeckt, als ob jemand nur kurz weggefahren wäre und bald zurückkommen wollte.',
          'Im Arbeitszimmer fand Jonas einen Schreibtisch aus dunklem Holz. Eine der Schubladen klemmte. Nachdem er eine Weile daran gezogen hatte, sprang sie plötzlich auf.',
          'Darin lag ein Umschlag mit seinem Namen. Die Handschrift war zittrig, aber gut lesbar: „Lieber Jonas, wenn du diesen Brief liest, weißt du noch nicht, warum ich gerade dir dieses Haus hinterlassen habe.“',
          'Jonas setzte sich auf den staubigen Stuhl und las weiter. Draußen begann es zu regnen, und die Tropfen klopften leise gegen das Fenster, während er die Geschichte seiner Familie zum ersten Mal wirklich verstand.',
        ],
      },
    ],
  },
  {
    id: 'die-nachricht',
    title: 'Die Nachricht',
    author: 'Lesefreund',
    level: 'B2',
    premium: true,
    color: '#e76f51',
    emoji: '📱',
    description: {
      ru: 'Одно сообщение меняет жизнь молодой журналистки. Konjunktiv II, сложные конструкции.',
      en: 'One message changes the life of a young journalist. Konjunktiv II, complex structures.',
    },
    chapters: [
      {
        title: 'Mitternacht',
        paragraphs: [
          'Hätte Miriam ihr Handy an jenem Abend ausgeschaltet, wäre ihr Leben vermutlich in ruhigen Bahnen verlaufen. Stattdessen leuchtete kurz nach Mitternacht der Bildschirm auf, und eine Nachricht von einer unbekannten Nummer erschien.',
          '„Sie recherchieren in die falsche Richtung“, stand dort. „Wenn Sie die Wahrheit über das Bauprojekt erfahren wollen, kommen Sie morgen um acht zum alten Hafen.“',
          'Miriam arbeitete seit knapp zwei Jahren als Lokaljournalistin, und obwohl sie sich oft nach einer großen Geschichte gesehnt hatte, war ihr bei dem Gedanken an ein anonymes Treffen alles andere als wohl.',
        ],
      },
      {
        title: 'Der Hafen',
        paragraphs: [
          'Am nächsten Morgen lag dichter Nebel über dem Wasser. Miriam hatte ihrer Kollegin Bescheid gegeben, wo sie sich aufhalten würde – für den Fall, dass etwas schiefginge.',
          'Ein älterer Mann in einem grauen Mantel wartete bereits an der Kaimauer. Er wirkte nervös und sah sich ständig um, als befürchte er, beobachtet zu werden.',
          '„Ich habe dreißig Jahre für die Stadtverwaltung gearbeitet“, begann er ohne Umschweife. „Was ich Ihnen jetzt erzähle, darf niemand mit mir in Verbindung bringen.“',
          'Er reichte ihr einen USB-Stick. „Darauf finden Sie alles. Gutachten, die nie veröffentlicht wurden, und E-Mails, die belegen, dass die Risiken von Anfang an bekannt waren.“ Bevor Miriam auch nur eine Frage stellen konnte, war er im Nebel verschwunden.',
        ],
      },
    ],
  },
  {
    id: 'sterntaler',
    title: 'Die Sterntaler',
    author: 'Brüder Grimm',
    level: 'B2',
    premium: true,
    color: '#264653',
    emoji: '✨',
    description: {
      ru: 'Классическая сказка братьев Гримм в оригинале (1812). Старинный язык.',
      en: 'The classic Brothers Grimm fairy tale in the original (1812). Old-fashioned language.',
    },
    chapters: [
      {
        title: 'Die Sterntaler',
        paragraphs: [
          'Es war einmal ein kleines Mädchen, dem war Vater und Mutter gestorben, und es war so arm, dass es kein Kämmerchen mehr hatte, darin zu wohnen, und kein Bettchen mehr, darin zu schlafen, und endlich gar nichts mehr als die Kleider auf dem Leib und ein Stückchen Brot in der Hand, das ihm ein mitleidiges Herz geschenkt hatte.',
          'Es war aber gut und fromm. Und weil es so von aller Welt verlassen war, ging es im Vertrauen auf den lieben Gott hinaus ins Feld.',
          'Da begegnete ihm ein armer Mann, der sprach: „Ach, gib mir etwas zu essen, ich bin so hungrig.“ Es reichte ihm das ganze Stückchen Brot und sagte: „Gott segne dir’s“, und ging weiter.',
          'Da kam ein Kind, das jammerte und sprach: „Es friert mich so an meinem Kopfe, schenk mir etwas, womit ich ihn bedecken kann.“ Da tat es seine Mütze ab und gab sie ihm.',
          'Und als es noch eine Weile gegangen war, kam wieder ein Kind und hatte kein Leibchen an und fror: da gab es ihm seins; und noch weiter, da bat eins um ein Röcklein, das gab es auch von sich hin.',
          'Endlich gelangte es in einen Wald, und es war schon dunkel geworden, da kam noch eins und bat um ein Hemdlein, und das fromme Mädchen dachte: „Es ist dunkle Nacht, da sieht dich niemand, du kannst wohl dein Hemd weggeben“, und zog das Hemd ab und gab es auch noch hin.',
          'Und wie es so stand und gar nichts mehr hatte, fielen auf einmal die Sterne vom Himmel, und waren lauter harte blanke Taler; und ob es gleich sein Hemdlein weggegeben, so hatte es ein neues an, und das war vom allerfeinsten Linnen. Da sammelte es sich die Taler hinein und war reich für sein Lebtag.',
        ],
      },
    ],
  },
  {
    id: 'verwandlung',
    title: 'Die Verwandlung (Auszug)',
    author: 'Franz Kafka',
    level: 'C1',
    premium: true,
    color: '#3d405b',
    emoji: '🪲',
    description: {
      ru: 'Начало знаменитой новеллы Кафки (1915). Длинные предложения, литературный язык.',
      en: 'The opening of Kafka’s famous novella (1915). Long sentences, literary language.',
    },
    chapters: [
      {
        title: 'I',
        paragraphs: [
          'Als Gregor Samsa eines Morgens aus unruhigen Träumen erwachte, fand er sich in seinem Bett zu einem ungeheueren Ungeziefer verwandelt. Er lag auf seinem panzerartig harten Rücken und sah, wenn er den Kopf ein wenig hob, seinen gewölbten, braunen, von bogenförmigen Versteifungen geteilten Bauch, auf dessen Höhe sich die Bettdecke, zum gänzlichen Niedergleiten bereit, kaum noch erhalten konnte. Seine vielen, im Vergleich zu seinem sonstigen Umfang kläglich dünnen Beine flimmerten ihm hilflos vor den Augen.',
          '„Was ist mit mir geschehen?“, dachte er. Es war kein Traum. Sein Zimmer, ein richtiges, nur etwas zu kleines Menschenzimmer, lag ruhig zwischen den vier wohlbekannten Wänden.',
        ],
      },
    ],
  },
];

export const LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1'];
