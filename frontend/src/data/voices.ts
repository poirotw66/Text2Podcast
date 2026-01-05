// Voice data based on voice_list.md
export interface Voice {
  name: string
  gender: 'male' | 'female'
  filename: string
}

export const VOICES: Voice[] = [
  { name: 'Achernar', gender: 'female', filename: 'chirp3-hd-achernar.wav' },
  { name: 'Achird', gender: 'male', filename: 'chirp3-hd-achird.wav' },
  { name: 'Algenib', gender: 'male', filename: 'chirp3-hd-algenib.wav' },
  { name: 'Algieba', gender: 'male', filename: 'chirp3-hd-algieba.wav' },
  { name: 'Alnilam', gender: 'male', filename: 'chirp3-hd-alnilam.wav' },
  { name: 'Aoede', gender: 'female', filename: 'chirp3-hd-aoeda.wav' },
  { name: 'Autonoe', gender: 'female', filename: 'chirp3-hd-autonoe.wav' },
  { name: 'Callirrhoe', gender: 'female', filename: 'chirp3-hd-callirrhoe.wav' },
  { name: 'Charon', gender: 'male', filename: 'chirp3-hd-charon.wav' },
  { name: 'Despina', gender: 'female', filename: 'chirp3-hd-despina.wav' },
  { name: 'Enceladus', gender: 'male', filename: 'chirp3-hd-enceladus.wav' },
  { name: 'Erinome', gender: 'female', filename: 'chirp3-hd-erinome.wav' },
  { name: 'Fenrir', gender: 'male', filename: 'chirp3-hd-fenrir.wav' },
  { name: 'Gacrux', gender: 'female', filename: 'chirp3-hd-gacrux.wav' },
  { name: 'Iapetus', gender: 'male', filename: 'chirp3-hd-iapetus.wav' },
  { name: 'Kore', gender: 'female', filename: 'chirp3-hd-kore.wav' },
  { name: 'Laomedeia', gender: 'female', filename: 'chirp3-hd-laomedeia.wav' },
  { name: 'Leda', gender: 'female', filename: 'chirp3-hd-leda.wav' },
  { name: 'Puck', gender: 'male', filename: 'chirp3-hd-puck.wav' },
  { name: 'Pulcherrima', gender: 'female', filename: 'chirp3-hd-pulcherrima.wav' },
  { name: 'Rasalgethi', gender: 'male', filename: 'chirp3-hd-rasalgethi.wav' },
  { name: 'Sadachbia', gender: 'male', filename: 'chirp3-hd-sadachbia.wav' },
  { name: 'Sadaltager', gender: 'male', filename: 'chirp3-hd-sadaltager.wav' },
  { name: 'Schedar', gender: 'male', filename: 'chirp3-hd-schedar.wav' },
  { name: 'Sulafat', gender: 'female', filename: 'chirp3-hd-sulafat.wav' },
  { name: 'Umbriel', gender: 'male', filename: 'chirp3-hd-umbriel.wav' },
  { name: 'Vindemiatrix', gender: 'female', filename: 'chirp3-hd-vindemiatrix.wav' },
  { name: 'Zephyr', gender: 'female', filename: 'chirp3-hd-zephyr.wav' },
  { name: 'Zubenelgenubi', gender: 'male', filename: 'chirp3-hd-zubenelgenubi.wav' },
]

export const DEFAULT_VOICES = {
  'Speaker 1': 'Kore',
  'Speaker 2': 'Charon'
}

