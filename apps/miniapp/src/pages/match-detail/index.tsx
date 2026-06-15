import { useEffect, useState } from 'react'
import { Text, View } from '@tarojs/components'
import { AIReportCard } from '@/components/AIReportCard'
import { BottomNav } from '@/components/BottomNav'
import { EvidenceList } from '@/components/EvidenceList'
import { ProbabilitySummary } from '@/components/ProbabilitySummary'
import { ProgressRow } from '@/components/ProgressRow'
import { ScorelineDistribution } from '@/components/ScorelineDistribution'
import { Section } from '@/components/Section'
import { StatusView } from '@/components/StatusView'
import { getMatchData, type LoadState } from '@/services/data'
import { featuredMatch, type Match } from '@/services/mock'

export default function MatchDetailPage() {
  const [match, setMatch] = useState<Match>(featuredMatch)
  const [updatedAt, setUpdatedAt] = useState('更新于 18:00')
  const [loadState, setLoadState] = useState<LoadState>('idle')

  useEffect(() => {
    let mounted = true
    setLoadState('loading')
    getMatchData()
      .then(data => {
        if (mounted) {
          setMatch(data.match)
          setUpdatedAt(data.updatedAt)
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
        <Text className='page-head__title'>AI 赛前报告</Text>
        <Text className='page-head__subtitle'>{match.status} · {updatedAt}</Text>
      </View>

      {loadState === 'loading' && <StatusView title='正在更新赛前报告' detail='稍后显示最新预测快照' />}
      {loadState === 'error' && <StatusView title='赛前报告暂未更新' detail='当前显示本地预测快照' />}

      <View className='surface'>
        <Text className='chip chip--warning'>{match.confidence}</Text>
        <Text className='match-title'>{match.home} vs {match.away}</Text>
        <Text className='match-meta'>{match.stage} · {match.time} · {match.venue}</Text>
        <ProbabilitySummary probabilities={match.probabilities} />
      </View>

      <Section title='AI 结论'>
        <AIReportCard title='核心判断' status='模型 + 情报'>
          {match.insight}
        </AIReportCard>
      </Section>

      <Section title='关键证据'>
        <EvidenceList items={match.evidence} />
      </Section>

      <Section title='比分分布'>
        <ScorelineDistribution items={match.scorelines} />
      </Section>

      <Section title='出线影响'>
        <ProgressRow label='美国胜后出线概率变化' value={18} meta='+18%' />
        <ProgressRow label='平局后出线概率变化' value={6} meta='+6%' />
        <ProgressRow label='失利后出线概率变化' value={21} meta='-21%' />
      </Section>

      <BottomNav active='matches' />
    </View>
  )
}
