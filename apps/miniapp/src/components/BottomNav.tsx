import { Text, View } from '@tarojs/components'
import { routes, switchSection } from '@/utils/navigation'

type TabKey = 'matches' | 'groups' | 'predictions' | 'teams'

const tabs: Array<{ key: TabKey; label: string; url: string }> = [
  { key: 'matches', label: '比赛', url: routes.matches },
  { key: 'groups', label: '小组', url: routes.groups },
  { key: 'predictions', label: '预测', url: routes.predictions },
  { key: 'teams', label: '球队', url: routes.teamDetail }
]

export function BottomNav({ active }: { active: TabKey }) {
  return (
    <View className='bottom-nav'>
      {tabs.map(tab => (
        <View
          key={tab.key}
          className={`bottom-nav__item ${active === tab.key ? 'bottom-nav__item--active' : ''}`}
          onClick={() => active !== tab.key && switchSection(tab.url)}
        >
          <Text>{tab.label}</Text>
        </View>
      ))}
    </View>
  )
}

