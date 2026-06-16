import { useEffect, useMemo, useState } from 'react'
import { Text, View } from '@tarojs/components'
import { BottomNav } from '@/components/BottomNav'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { ProgressRow } from '@/components/ProgressRow'
import { getRankingData, type LoadState } from '@/services/data'
import { championRankings, darkHorseRankings, semiFinalRankings, type RankingTeam } from '@/services/mock'
import { getTeamIdByName } from '@/services/teamResources'
import { goTo, routes } from '@/utils/navigation'

const rankingMap = {
  champion: championRankings,
  semifinal: semiFinalRankings,
  darkhorse: darkHorseRankings
}

const tabLabels = {
  champion: '冠军',
  semifinal: '四强',
  darkhorse: '黑马'
}

type Tab = keyof typeof rankingMap

function sourceLabel(active: Tab) {
  if (active === 'champion') return '基于 50,000 次模拟'
  if (active === 'semifinal') return '四强路径模拟'
  return '黑马上限评估'
}

export default function PredictionsPage() {
  const [active, setActive] = useState<Tab>('champion')
  const [rankings, setRankings] = useState<RankingTeam[]>(rankingMap[active])
  const [rankingMeta, setRankingMeta] = useState({ updatedAt: '更新于 18:00', source: sourceLabel(active) })
  const [loadState, setLoadState] = useState<LoadState>('idle')

  useEffect(() => {
    let mounted = true
    setRankings(rankingMap[active])
    setRankingMeta({ updatedAt: '更新于 18:00', source: sourceLabel(active) })
    setLoadState('loading')
    getRankingData(active)
      .then(data => {
        if (!mounted) return
        setRankings(data.rankings.length ? data.rankings : rankingMap[active])
        setRankingMeta({
          updatedAt: data.updatedAt && !data.updatedAt.includes('待') ? data.updatedAt.replace('数据更新于 ', '更新于 ') : '更新于 18:00',
          source: data.source && !data.source.includes('待') ? data.source : sourceLabel(active)
        })
        setLoadState('ready')
      })
      .catch(() => {
        if (!mounted) return
        setRankings(rankingMap[active])
        setRankingMeta({ updatedAt: '更新于 18:00', source: sourceLabel(active) })
        setLoadState('error')
      })

    return () => {
      mounted = false
    }
  }, [active])

  const displayRankings = useMemo(() => rankings.length ? rankings : rankingMap[active], [active, rankings])
  const topTeam = displayRankings[0]

  return (
    <View className='page page--predictions design-page'>
      <View className='ranking-header'>
        <View>
          <Text className='app-title'>预测榜</Text>
          <Text className='page-head__subtitle'>{rankingMeta.source}</Text>
        </View>
        <View className='ranking-header__updated'>
          <Icon name='clock' color='#6b7280' size={28} />
          <Text>{rankingMeta.updatedAt}</Text>
        </View>
      </View>

      <View className='segmented segmented--design'>
        {Object.keys(tabLabels).map(key => (
          <Text
            key={key}
            className={`segmented__item ${active === key ? 'segmented__item--active' : ''}`}
            onClick={() => setActive(key as Tab)}
          >
            {tabLabels[key as Tab]}
          </Text>
        ))}
      </View>

      <View className='ranking-ai-card ranking-ai-card--design'>
        <View>
          <View className='ranking-ai-card__title'>
            <Icon name='ai' color='#2563eb' size={42} />
            <Text>AI 榜单解读</Text>
          </View>
          <Text className='ranking-ai-card__text'>
            {topTeam ? `${topTeam.name}仍是${tabLabels[active]}概率最高球队，${displayRankings[1]?.name || '第二集团'}和${displayRankings[2]?.name || '第三集团'}差距很小。` : '榜单等待模型生成。'}
          </Text>
        </View>
        <View className='ranking-ai-card__art'>
          <View className='ranking-ai-orbit'>
            <View className='ranking-ai-orbit__core'>
              <Icon name='ai' color='#2563eb' size={58} />
            </View>
            <View className='ranking-ai-orbit__satellite ranking-ai-orbit__satellite--top'>
              <Icon name='ai' color='#ffffff' size={24} />
            </View>
            <View className='ranking-ai-orbit__satellite ranking-ai-orbit__satellite--bottom'>
              <Icon name='chart' color='#2563eb' size={24} />
            </View>
          </View>
        </View>
      </View>

      <View className='ranking-table-card'>
        <View className='ranking-table-head'>
          <Text>排名 / 球队</Text>
          <Text>{tabLabels[active]}概率</Text>
          <Text>较昨日变化</Text>
        </View>
        {displayRankings.map(team => (
          <View
            className='ranking-row ranking-row--table'
            key={team.name}
            onClick={() => goTo(`${routes.teamDetail}?teamId=${team.teamId || getTeamIdByName(team.name)}&source=predictions&rankingType=${active}`)}
          >
            <View className='ranking-row__team-block'>
              <Text className='ranking-row__rank'>{team.rank}</Text>
              <View className='ranking-row__divider' />
              <Flag team={team.name} size='sm' />
              <View className='ranking-row__name-wrap'>
                <Text className='ranking-row__name'>{team.name}</Text>
                <Text className='reason-chip'>{team.reason}</Text>
              </View>
            </View>
            <View className='ranking-row__probability-block'>
              <Text className='ranking-row__probability'>{team.probability}%</Text>
              <ProgressRow label='' value={team.probability} />
            </View>
            <View className='ranking-row__change-block'>
              <Text className={team.delta >= 0 ? 'delta delta--up' : 'delta delta--down'}>
                {team.delta >= 0 ? '▲' : '▼'} {Math.abs(team.delta)}%
              </Text>
            </View>
          </View>
        ))}
      </View>

      <View className='today-change-card today-change-card--design' onClick={() => goTo(routes.matches)}>
        <View className='today-change-card__icon'>
          <Icon name='chart' color='#2563eb' size={36} />
        </View>
        <View className='today-change-card__main'>
          <Text className='today-change-card__title'>今日变化</Text>
          <Text className='today-change-card__text'>
            美国胜率上调，带动出线概率 <Text className='text-positive'>+18%</Text>
          </Text>
          <Text className='today-change-card__meta'>战胜巴拉圭概率上升，出线形势明显改善。</Text>
        </View>
        <Icon name='chevron' color='#94a3b8' size={30} />
      </View>

      {loadState === 'error' ? <Text className='data-note'>后端未连接，当前使用设计稿样例数据。</Text> : null}
      <BottomNav active='predictions' />
    </View>
  )
}
