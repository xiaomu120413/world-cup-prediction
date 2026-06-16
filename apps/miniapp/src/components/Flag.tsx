import { useEffect, useState } from 'react'
import { Image, View } from '@tarojs/components'
import { getLocalFlagAsset } from '@/assets/flags'
import fallbackFlag from '@/assets/flags/fallback.svg'
import { getFlagCodeByTeamName } from '@/services/teamResources'

export function Flag({ team, size = 'md' }: { team: string; size?: 'sm' | 'md' | 'lg' }) {
  const code = getFlagCodeByTeamName(team)
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
