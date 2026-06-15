import { useEffect, useState } from 'react'
import { Text, View } from '@tarojs/components'
import { AIReportCard } from '@/components/AIReportCard'
import { BottomNav } from '@/components/BottomNav'
import { ProgressRow } from '@/components/ProgressRow'
import { Section } from '@/components/Section'
import { StatusView } from '@/components/StatusView'
import { getGroupData, type GroupData, type LoadState } from '@/services/data'
import { groupATeams } from '@/services/mock'
import { goTo, routes } from '@/utils/navigation'

const fallbackGroup: GroupData = {
  title: 'A组形势',
  subtitle: '小组赛 · 已完成 2/6 场',
  summary: '墨西哥和韩国出线优势明显，捷克仍保留第三名晋级机会。',
  teams: groupATeams,
  updatedAt: '模拟更新于 18:00'
}

export default function GroupsPage() {
  const [groupData, setGroupData] = useState<GroupData>(fallbackGroup)
  const [loadState, setLoadState] = useState<LoadState>('idle')

  useEffect(() => {
    let mounted = true
    setLoadState('loading')
    getGroupData()
      .then(data => {
        if (mounted) {
          setGroupData(data)
          setLoadState('ready')
        }
      })
      .catch(() => {
        if (mounted) {
          setLoadState('error')
        }
      })

    return () => {
      mounted = false
    }
  }, [])

  return (
    <View className='page'>
      <View className='page-head'>
        <Text className='page-head__title'>{groupData.title}</Text>
        <Text className='page-head__subtitle'>{groupData.subtitle}</Text>
        <Text className='muted'>{groupData.updatedAt}</Text>
      </View>

      {loadState === 'loading' && <StatusView title='正在更新小组形势' detail='稍后显示最新模拟快照' />}
      {loadState === 'error' && <StatusView title='小组形势暂未更新' detail='当前显示本地模拟快照' />}

      <Section title='AI 小组判断'>
        <AIReportCard title='出线形势'>
          {groupData.summary}
        </AIReportCard>
      </Section>

      <Section title='积分榜'>
        {groupData.teams.map(team => (
          <View className='table-row' key={team.name} onClick={() => goTo(routes.teamDetail)}>
            <Text className='table-row__rank'>{team.rank}</Text>
            <View>
              <Text className='table-row__team'>{team.name}</Text>
              <Text className='table-row__meta'>{team.record}</Text>
            </View>
            <Text className='table-row__meta'>{team.goals}</Text>
            <Text className='table-row__points'>{team.points}分</Text>
          </View>
        ))}
      </Section>

      <Section title='出线概率'>
        {groupData.teams.map(team => (
          <ProgressRow key={team.name} label={team.name} value={team.qualification} />
        ))}
      </Section>

      <Section title='关键赛程'>
        <View className='list-row' onClick={() => goTo(routes.matchDetail)}>
          <Text className='list-row__title'>墨西哥 vs 韩国</Text>
          <Text className='list-row__right'>小组头名战</Text>
        </View>
        <View className='list-row' onClick={() => goTo(routes.matchDetail)}>
          <Text className='list-row__title'>捷克 vs 南非</Text>
          <Text className='list-row__right'>第三名关键战</Text>
        </View>
      </Section>

      <BottomNav active='groups' />
    </View>
  )
}
