import { useEffect, useState } from 'react'
import { Image, View } from '@tarojs/components'
import { getLocalFlagAsset } from '@/assets/flags'
import fallbackFlag from '@/assets/flags/fallback.svg'
import { getFlagCodeByTeamName } from '@/services/teamResources'

export function Flag({ team, size = 'md' }: { team: string; size?: 'sm' | 'md' | 'lg' }) {
  const code = getFlagCodeByTeamName(team)
  const flagSrc = getLocalFlagAsset(code) || fallbackFlag
  const [src, setSrc] = useState(flagSrc)

  useEffect(() => {
    setSrc(flagSrc)
  }, [flagSrc])

  return (
    <View className={`flag flag--${size}`}>
      <Image src={src} mode='aspectFit' className='flag__image' onError={() => setSrc(fallbackFlag)} />
    </View>
  )
}
