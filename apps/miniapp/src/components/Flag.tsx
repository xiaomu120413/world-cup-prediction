import { useEffect, useState } from 'react'
import { Image, View } from '@tarojs/components'
import { getLocalFlagAsset } from '@/assets/flags'
import fallbackFlag from '@/assets/flags/fallback.svg'
import { getFlagCodeByTeam } from '@/services/teamResources'

type FlagProps = {
  team?: string
  teamId?: string | null
  teamCode?: string | null
  teamEn?: string | null
  size?: 'sm' | 'md' | 'lg'
}

export function Flag({ team, teamId, teamCode, teamEn, size = 'md' }: FlagProps) {
  const code = getFlagCodeByTeam({
    id: teamId,
    code: teamCode,
    name: team,
    nameEn: teamEn
  })
  const flagSrc = getLocalFlagAsset(code) || fallbackFlag
  const [src, setSrc] = useState(flagSrc)
  const fillMode = size === 'lg'

  useEffect(() => {
    setSrc(flagSrc)
  }, [flagSrc])

  return (
    <View className={`flag flag--${size} ${fillMode ? 'flag--cover' : 'flag--contain'}`}>
      <Image src={src} mode={fillMode ? 'aspectFill' : 'aspectFit'} className='flag__image' onError={() => setSrc(fallbackFlag)} />
    </View>
  )
}
