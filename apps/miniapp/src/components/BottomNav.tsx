import { Text, View } from '@tarojs/components'
import { Icon } from '@/components/Icon'
import { routes, switchSection } from '@/utils/navigation'

type TabKey = 'matches' | 'groups' | 'predictions' | 'teams'

const tabs: Array<{ key: TabKey; label: string; url: string; icon: 'ball' | 'trophy' | 'chart' | 'shield' }> = [
  { key: 'matches', label: '比赛', url: routes.matches, icon: 'ball' },
  { key: 'groups', label: '小组', url: routes.groups, icon: 'trophy' },
  { key: 'predictions', label: '预测', url: routes.predictions, icon: 'chart' },
  { key: 'teams', label: '球队', url: routes.teamDetail, icon: 'shield' }
]

export function BottomNav({ active }: { active: TabKey }) {
  return (
    <View className='bottom-nav'>
      {tabs.map(tab => (
        <View
          key={tab.key}
          data-testid={`bottom-nav-${tab.key}`}
          className={`bottom-nav__item ${active === tab.key ? 'bottom-nav__item--active' : ''}`}
          onClick={() => active !== tab.key && switchSection(tab.url)}
        >
          <Icon name={tab.icon} color={active === tab.key ? '#2563eb' : '#6b7280'} size={36} />
          <Text>{tab.label}</Text>
        </View>
      ))}
    </View>
  )
}
