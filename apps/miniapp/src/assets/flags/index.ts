import flagAr from './ar.png'
import flagAt from './at.png'
import flagAu from './au.png'
import flagBa from './ba.png'
import flagBe from './be.png'
import flagBr from './br.png'
import flagCa from './ca.png'
import flagCd from './cd.png'
import flagCh from './ch.png'
import flagCi from './ci.png'
import flagCo from './co.png'
import flagCv from './cv.png'
import flagCw from './cw.png'
import flagCz from './cz.png'
import flagDe from './de.png'
import flagDk from './dk.png'
import flagDz from './dz.png'
import flagEc from './ec.png'
import flagEg from './eg.png'
import flagEs from './es.png'
import flagFr from './fr.png'
import flagGbEng from './gb-eng.png'
import flagGbSct from './gb-sct.png'
import flagGh from './gh.png'
import flagHr from './hr.png'
import flagHt from './ht.png'
import flagIq from './iq.png'
import flagIr from './ir.png'
import flagIt from './it.png'
import flagJo from './jo.png'
import flagJp from './jp.png'
import flagKr from './kr.png'
import flagMa from './ma.png'
import flagMx from './mx.png'
import flagNl from './nl.png'
import flagNo from './no.png'
import flagNz from './nz.png'
import flagPa from './pa.png'
import flagPt from './pt.png'
import flagPy from './py.png'
import flagQa from './qa.png'
import flagSa from './sa.png'
import flagSe from './se.png'
import flagSn from './sn.png'
import flagTn from './tn.png'
import flagTr from './tr.png'
import flagUs from './us.png'
import flagUy from './uy.png'
import flagUz from './uz.png'
import flagZa from './za.png'

export const localFlagAssets: Record<string, string> = {
  'ar': flagAr,
  'at': flagAt,
  'au': flagAu,
  'ba': flagBa,
  'be': flagBe,
  'br': flagBr,
  'ca': flagCa,
  'cd': flagCd,
  'ch': flagCh,
  'ci': flagCi,
  'co': flagCo,
  'cv': flagCv,
  'cw': flagCw,
  'cz': flagCz,
  'de': flagDe,
  'dk': flagDk,
  'dz': flagDz,
  'ec': flagEc,
  'eg': flagEg,
  'es': flagEs,
  'fr': flagFr,
  'gb-eng': flagGbEng,
  'gb-sct': flagGbSct,
  'gh': flagGh,
  'hr': flagHr,
  'ht': flagHt,
  'iq': flagIq,
  'ir': flagIr,
  'it': flagIt,
  'jo': flagJo,
  'jp': flagJp,
  'kr': flagKr,
  'ma': flagMa,
  'mx': flagMx,
  'nl': flagNl,
  'no': flagNo,
  'nz': flagNz,
  'pa': flagPa,
  'pt': flagPt,
  'py': flagPy,
  'qa': flagQa,
  'sa': flagSa,
  'se': flagSe,
  'sn': flagSn,
  'tn': flagTn,
  'tr': flagTr,
  'us': flagUs,
  'uy': flagUy,
  'uz': flagUz,
  'za': flagZa
}

export function getLocalFlagAsset(code?: string) {
  return code ? localFlagAssets[code] : undefined
}
