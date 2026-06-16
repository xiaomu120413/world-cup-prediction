import { useEffect, useMemo, useState } from 'react'
import { Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { BottomNav } from '@/components/BottomNav'
import { EvidenceList } from '@/components/EvidenceList'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { ProbabilitySummary } from '@/components/ProbabilitySummary'
import { ScorelineDistribution } from '@/components/ScorelineDistribution'
import { Section } from '@/components/Section'
import { getMatchData, type LoadState } from '@/services/data'
import { featuredMatch, type Match } from '@/services/mock'

function getRouteMatchId() {
  const params = Taro.getCurrentInstance().router?.params
  const value = params?.matchId
  return typeof value === 'string' && value ? value : undefined
}

function shouldUseDesignMatch(match: Match) {
  return !match.probabilities.length || match.id === 'pending-match' || match.home.includes('待')
}

export default function MatchDetailPage() {
  const [matchId] = useState(getRouteMatchId)
  const [match, setMatch] = useState<Match>(featuredMatch)
  const [updatedAt, setUpdatedAt] = useState('数据更新于 18:00')
  const [loadState, setLoadState] = useState<LoadState>('idle')

  useEffect(() => {
    let mounted = true
    setLoadState('loading')
    getMatchData(matchId)
      .then(data => {
        if (!mounted) return
        setMatch(data.match)
        setUpdatedAt(data.updatedAt && !data.updatedAt.includes('待') ? data.updatedAt : '数据更新于 18:00')
        setLoadState('ready')
      })
      .catch(() => {
        if (!mounted) return
        setMatch(featuredMatch)
        setUpdatedAt('数据更新于 18:00')
        setLoadState('error')
      })

    return () => {
      mounted = false
    }
  }, [matchId])

  const displayMatch = useMemo(() => shouldUseDesignMatch(match) ? featuredMatch : match, [match])

  return (
    <View className='page page--report design-page'>
      <View className='report-header report-header--large'>
        <View className='report-header__brand'>
          <View className='report-logo'>
            <Icon name='ai' color='#ffffff' size={36} />
          </View>
          <Text className='app-title'>AI 赛前报告</Text>
        </View>
        <View className='share-pill'>
          <Icon name='share' color='#0f172a' size={28} />
          <Text>分享报告</Text>
        </View>
      </View>

      <View className='match-card match-card--report'>
        <View className='fixture fixture--report'>
          <View className='fixture__team'>
            <Flag team={displayMatch.home} size='lg' />
            <Text className='fixture__name'>{displayMatch.home}</Text>
          </View>
          <View className='fixture__middle'>
            <Text className='fixture__vs'>VS</Text>
            <Text className='fixture__time'>{displayMatch.versionLabel || '最终赛前版'} · {updatedAt.replace('数据更新于 ', '更新于 ')}</Text>
          </View>
          <View className='fixture__team fixture__team--away'>
            <Flag team={displayMatch.away} size='lg' />
            <Text className='fixture__name'>{displayMatch.away}</Text>
          </View>
        </View>
      </View>

      <View className='surface probability-card probability-card--report'>
        <View className='surface-head'>
          <View className='section-title-with-info'>
            <Text className='section__title'>胜平负概率</Text>
            <Icon name='info' color='#64748b' size={26} />
          </View>
          <Text className='confidence-pill'>{displayMatch.confidence}</Text>
        </View>
        <ProbabilitySummary probabilities={displayMatch.probabilities} />
        <View className='probability-bar-strip'>
          {displayMatch.probabilities.map(item => (
            <View
              key={item.label}
              className={`probability-bar-strip__item ${item.label.includes('平') ? 'probability-bar-strip__item--draw' : item.label.includes(displayMatch.away) ? 'probability-bar-strip__item--away' : ''}`}
              style={{ width: `${item.value}%` }}
            />
          ))}
        </View>
      </View>

      <View className='analyst-card'>
        <View className='analyst-card__head'>
          <View className='analyst-card__avatar'>
            <Icon name='bot' color='#2563eb' size={44} />
          </View>
          <Text>AI 分析师</Text>
        </View>
        <Text className='analyst-card__text'>{displayMatch.insight}</Text>
      </View>

      <Section title='关键证据' action=''>
        <EvidenceList items={displayMatch.evidence} />
        <Text className='section-footnote'>注：正值提升美国胜概率，负值提升平局和巴拉圭胜概率</Text>
      </Section>

      <Section title='比分分布（概率最高）'>
        <ScorelineDistribution items={displayMatch.scorelines} />
      </Section>

      <View className='impact-card impact-card--design'>
        <View className='impact-card__icon impact-card__icon--green'>
          <Icon name='trophy' color='#16a34a' size={40} />
        </View>
        <View className='impact-card__content'>
          <Text className='impact-card__title'>出线影响</Text>
          <Text className='impact-card__text'>{displayMatch.home}胜后出线概率</Text>
        </View>
        <Text className='impact-card__value'>+18%</Text>
        <Icon name='chevron' color='#94a3b8' size={32} />
      </View>

      <Text className='data-note'>* 数据基于截至当前的公开信息与模型推算，仅供参考。</Text>
      {loadState === 'error' ? <Text className='data-note'>后端未连接，当前使用设计稿样例数据。</Text> : null}
      <BottomNav active='predictions' />
    </View>
  )
}
