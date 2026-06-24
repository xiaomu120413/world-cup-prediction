import { useEffect, useState } from 'react'
import { Button, Text, View } from '@tarojs/components'
import Taro, { useShareAppMessage } from '@tarojs/taro'
import { BottomNav } from '@/components/BottomNav'
import { EvidenceList } from '@/components/EvidenceList'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { ProbabilitySummary } from '@/components/ProbabilitySummary'
import { ScorelineDistribution } from '@/components/ScorelineDistribution'
import { Section } from '@/components/Section'
import { getMatchData, type LoadState } from '@/services/data'
import type { Match } from '@/services/types'

function getRouteMatchId() {
  const params = Taro.getCurrentInstance().router?.params
  const value = params?.matchId
  return typeof value === 'string' && value ? value : undefined
}

export default function MatchDetailPage() {
  const [matchId] = useState(getRouteMatchId)
  const [match, setMatch] = useState<Match | null>(null)
  const [updatedAt, setUpdatedAt] = useState('')
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [shareLabel, setShareLabel] = useState('分享报告')
  const sharePath = `/pages/match-detail/index?matchId=${encodeURIComponent(match?.id || matchId || '')}`
  const shareTitle = match ? `${match.home} vs ${match.away} AI 赛前报告` : '世界杯 AI 赛前报告'

  useShareAppMessage(() => ({
    title: shareTitle,
    path: sharePath,
  }))

  useEffect(() => {
    let mounted = true
    setLoadState('loading')
    getMatchData(matchId)
      .then(data => {
        if (!mounted) return
        setMatch(data.match)
        setUpdatedAt(data.updatedAt)
        setLoadState('ready')
      })
      .catch(() => {
        if (!mounted) return
        setMatch(null)
        setUpdatedAt('')
        setLoadState('error')
      })

    return () => {
      mounted = false
    }
  }, [matchId])

  async function handleShareClick() {
    if (process.env.TARO_ENV === 'weapp') {
      return
    }
    const url = typeof window !== 'undefined' ? window.location.href : sharePath
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url)
      } else {
        await Taro.setClipboardData({ data: url })
      }
      setShareLabel('已复制')
      Taro.showToast({ title: '链接已复制', icon: 'success' })
      window.setTimeout(() => setShareLabel('分享报告'), 1800)
    } catch {
      setShareLabel('复制失败')
      Taro.showToast({ title: '复制失败', icon: 'none' })
      window.setTimeout(() => setShareLabel('分享报告'), 1800)
    }
  }

  if (!match) {
    return (
      <View className='page page--report design-page'>
        <View className='report-header report-header--large'>
          <View className='report-header__brand'>
            <View className='report-logo'>
              <Icon name='ai' color='#ffffff' size={36} />
            </View>
            <Text className='app-title'>AI 赛前报告</Text>
          </View>
        </View>
        <View className='empty-state'>
          <Text>{loadState === 'loading' ? '正在加载比赛数据' : '比赛数据暂不可用'}</Text>
        </View>
        <BottomNav active='predictions' />
      </View>
    )
  }

  return (
    <View className='page page--report design-page'>
      <View className='report-header report-header--large'>
        <View className='report-header__brand'>
          <View className='report-logo'>
            <Icon name='ai' color='#ffffff' size={36} />
          </View>
          <Text className='app-title'>AI 赛前报告</Text>
        </View>
        <Button
          className='share-pill'
          openType={process.env.TARO_ENV === 'weapp' ? 'share' : undefined}
          hoverClass='share-pill--hover'
          onClick={handleShareClick}
        >
          <Icon name='share' color='#0f172a' size={28} />
          <Text>{shareLabel}</Text>
        </Button>
      </View>

      <View className='match-card match-card--report'>
        <View className='fixture fixture--report'>
          <View className='fixture__team'>
            <Flag team={match.home} size='lg' />
            <Text className='fixture__name'>{match.home}</Text>
          </View>
          <View className='fixture__middle'>
            <Text className='fixture__vs'>VS</Text>
            <Text className='fixture__time'>{match.versionLabel || match.status} · {updatedAt.replace('数据更新于 ', '更新于 ')}</Text>
          </View>
          <View className='fixture__team fixture__team--away'>
            <Flag team={match.away} size='lg' />
            <Text className='fixture__name'>{match.away}</Text>
          </View>
        </View>
      </View>

      <View className='surface probability-card probability-card--report'>
        <View className='surface-head'>
          <View className='section-title-with-info'>
            <Text className='section__title'>胜平负概率</Text>
            <Icon name='info' color='#64748b' size={26} />
          </View>
          <Text className='confidence-pill'>{match.confidence}</Text>
        </View>
        <ProbabilitySummary probabilities={match.probabilities} />
        <View className='probability-bar-strip'>
          {match.probabilities.map(item => (
            <View
              key={item.label}
              className={`probability-bar-strip__item ${item.label.includes('平') ? 'probability-bar-strip__item--draw' : item.label.includes(match.away) ? 'probability-bar-strip__item--away' : ''}`}
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
          <Text>AI 中文解读</Text>
        </View>
        <Text className='analyst-card__text'>{match.insight}</Text>
      </View>

      <Section title='关键证据' action=''>
        <EvidenceList items={match.evidence} />
        <Text className='section-footnote'>证据来自赛前预测快照和公开数据源。</Text>
      </Section>

      <Section title='比分分布'>
        <ScorelineDistribution items={match.scorelines} />
      </Section>

      <Text className='data-note'>* 概率会随赛果、阵容、伤停和天气更新。</Text>
      {loadState === 'error' ? <Text className='data-note'>数据连接异常，请稍后重试。</Text> : null}
      <BottomNav active='predictions' />
    </View>
  )
}
