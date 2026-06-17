import { useEffect, useMemo, useState } from 'react'
import { Text, View } from '@tarojs/components'
import { BottomNav } from '@/components/BottomNav'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { ProgressRow } from '@/components/ProgressRow'
import { getRankingData, type LoadState } from '@/services/data'
import type { RankingTeam } from '@/services/types'
import { goTo, routes } from '@/utils/navigation'

const tabLabels = {
  champion: '冠军',
  semifinal: '四强',
  darkhorse: '黑马'
}

type Tab = keyof typeof tabLabels

export default function PredictionsPage() {
  const [active, setActive] = useState<Tab>('champion')
  const [rankings, setRankings] = useState<RankingTeam[]>([])
  const [rankingMeta, setRankingMeta] = useState({ updatedAt: '', source: '' })
  const [loadState, setLoadState] = useState<LoadState>('idle')

  useEffect(() => {
    let mounted = true
    setRankings([])
    setRankingMeta({ updatedAt: '', source: '' })
    setLoadState('loading')
    getRankingData(active)
      .then(data => {
        if (!mounted) return
        setRankings(data.rankings)
        setRankingMeta({
          updatedAt: data.updatedAt.replace('数据更新于 ', '更新于 '),
          source: data.source
        })
        setLoadState('ready')
      })
      .catch(() => {
        if (!mounted) return
        setRankings([])
        setRankingMeta({ updatedAt: '', source: '' })
        setLoadState('error')
      })

    return () => {
      mounted = false
    }
  }, [active])

  const topTeam = useMemo(() => rankings[0], [rankings])

  return (
    <View className='page page--predictions design-page'>
      <View className='ranking-header'>
        <View>
          <Text className='app-title'>预测榜</Text>
          <Text className='page-head__subtitle'>{rankingMeta.source || (loadState === 'loading' ? '加载真实预测数据' : '等待真实预测数据')}</Text>
        </View>
        <View className='ranking-header__updated'>
          <Icon name='clock' color='#6b7280' size={28} />
          <Text>{rankingMeta.updatedAt || '-'}</Text>
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
            {topTeam ? `${topTeam.name} 当前位列${tabLabels[active]}榜首，概率为 ${topTeam.probability}%。` : '暂无真实预测榜数据。'}
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
          <Text>变化</Text>
        </View>
        {rankings.length ? rankings.map(team => (
          <View
            className='ranking-row ranking-row--table'
            key={team.teamId || team.name}
            onClick={() => {
              if (team.teamId) {
                goTo(`${routes.teamDetail}?teamId=${team.teamId}&source=predictions&rankingType=${active}`)
              }
            }}
          >
            <View className='ranking-row__team-block'>
              <Text className='ranking-row__rank'>{team.rank}</Text>
              <View className='ranking-row__divider' />
              <Flag team={team.name} teamId={team.teamId} teamCode={team.teamCode} teamEn={team.nameEn} size='sm' />
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
        )) : <View className='empty-state'><Text>{loadState === 'loading' ? '正在加载真实榜单' : '暂无真实榜单数据'}</Text></View>}
      </View>

      <View className='today-change-card today-change-card--design' onClick={() => goTo(routes.matches)}>
        <View className='today-change-card__icon'>
          <Icon name='chart' color='#2563eb' size={36} />
        </View>
        <View className='today-change-card__main'>
          <Text className='today-change-card__title'>数据状态</Text>
          <Text className='today-change-card__text'>
            {topTeam ? `${topTeam.name} 当前 ${tabLabels[active]}概率 ${topTeam.probability}%` : '真实预测快照暂不可用'}
          </Text>
          <Text className='today-change-card__meta'>{rankingMeta.updatedAt || '等待后端定时任务刷新'}</Text>
        </View>
        <Icon name='chevron' color='#94a3b8' size={30} />
      </View>

      {loadState === 'error' ? <Text className='data-note'>真实接口连接失败，未显示虚拟数据。</Text> : null}
      <BottomNav active='predictions' />
    </View>
  )
}
