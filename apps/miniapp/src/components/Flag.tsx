import { Image, Text, View } from '@tarojs/components'

const teamFlags: Record<string, string> = {
  美国: 'us',
  巴拉圭: 'py',
  卡塔尔: 'qa',
  瑞士: 'ch',
  巴西: 'br',
  摩洛哥: 'ma',
  法国: 'fr',
  挪威: 'no',
  墨西哥: 'mx',
  韩国: 'kr',
  捷克: 'cz',
  南非: 'za',
  英格兰: 'gb-eng',
  西班牙: 'es',
  阿根廷: 'ar',
  塞内加尔: 'sn'
}

export function Flag({ team, size = 'md' }: { team: string; size?: 'sm' | 'md' | 'lg' }) {
  const code = teamFlags[team]

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
