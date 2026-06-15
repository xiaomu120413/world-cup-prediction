import { Image, Text, View } from '@tarojs/components'
import { getFlagCodeByTeamName } from '@/services/teamResources'

export function Flag({ team, size = 'md' }: { team: string; size?: 'sm' | 'md' | 'lg' }) {
  const code = getFlagCodeByTeamName(team)

  return (
    <View className={`flag flag--${size}`}>
      {code ? (
        <Image src={`https://flagcdn.com/w80/${code}.png`} mode='aspectFill' className='flag__image' />
      ) : (
        <Text className='flag__fallback'>{team.slice(0, 1)}</Text>
      )}
    </View>
  )
}
