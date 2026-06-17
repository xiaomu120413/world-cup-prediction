import { useEffect, useMemo, useState } from 'react'
import { Text, View } from '@tarojs/components'
import { BottomNav } from '@/components/BottomNav'
import { Flag } from '@/components/Flag'
import { Icon } from '@/components/Icon'
import { ProbabilitySummary } from '@/components/ProbabilitySummary'
import { ProgressRow } from '@/components/ProgressRow'
import { Section } from '@/components/Section'
import { getHomeData, type HomeData, type LoadState } from '@/services/data'
import { goTo, routes } from '@/utils/navigation'

function splitKickoff(value: string) {
  const match = value.match(/^(.+)\s+(\d{2}:\d{2})$/)
  if (!match) {
    return { date: '', clock: value }
  }
  return { date: match[1], clock: match[2] }
}

export default function MatchesPage() {
  const [homeData, setHomeData] = useState<HomeData | null>(null)
  const [loadState, setLoadState] = useState<LoadState>('idle')

  useEffect(() => {
    let mounted = true
    setLoadState('loading')
    getHomeData()
      .then(data => {
        if (!mounted) return
        setHomeData(data)
        setLoadState('ready')
      })
      .catch(() => {
        if (!mounted) return
        setHomeData(null)
        setLoadState('error')
      })

    return () => {
      mounted = false
    }
  }, [])

  const display = useMemo(() => {
    if (!homeData) return null
    return {
      match: homeData.featuredMatch,
      upcoming: homeData.upcomingMatches,
      champions: homeData.championTop,
      updatedAt: homeData.updatedAt
    }
  }, [homeData])

  const openMatchDetail = () => {
    if (display?.match.id) {
      goTo(`${routes.matchDetail}?matchId=${display.match.id}`)
    }
  }

  return (
    <View className='page page--matchday design-page'>
      <View className='app-header app-header--home'>
        <Text className='app-title'>世界杯预测</Text>
        <View className='header-ai' onClick={openMatchDetail}>
          <Icon name='ai' color='#2563eb' size={30} />
          <Text>AI 赛前报告</Text>
        </View>
      </View>

      <View className='home-meta-row'>
        <View className='subline'>
          <View className='subline__bar' />
          <Text>真实赛程</Text>
        </View>
        <View className='updated-line updated-line--right'>
          <Icon name='clock' color='#6b7280' size={26} />
          <Text>{display?.updatedAt || (loadState === 'loading' ? '加载真实数据' : '等待真实数据')}</Text>
        </View>
      </View>

      {display?.match ? (
        <View className='focus-card' onClick={openMatchDetail}>
          <View className='focus-card__top'>
            <Text className='card-eyebrow'>今日重点</Text>
          </View>

          <View className='fixture fixture--hero'>
            <View className='fixture__team'>
              <Flag
                team={display.match.home}
                teamId={display.match.homeTeam?.teamId}
                teamCode={display.match.homeTeam?.teamCode}
                teamEn={display.match.homeTeam?.nameEn}
                size='lg'
              />
              <Text className='fixture__name'>{display.match.home}</Text>
            </View>
            <View className='fixture__middle'>
              <Text className='match-version-pill'>{display.match.versionLabel || display.match.status}</Text>
              <Text className='fixture__vs'>VS</Text>
              <Text className='fixture__time'>{display.match.time}</Text>
              <Text className='fixture__venue'>{display.match.venue}</Text>
            </View>
            <View className='fixture__team fixture__team--away'>
              <Flag
                team={display.match.away}
                teamId={display.match.awayTeam?.teamId}
                teamCode={display.match.awayTeam?.teamCode}
                teamEn={display.match.awayTeam?.nameEn}
                size='lg'
              />
              <Text className='fixture__name'>{display.match.away}</Text>
            </View>
          </View>

          <ProbabilitySummary probabilities={display.match.probabilities} />

          <View className='home-report-strip'>
            <View className='home-report-strip__head'>
              <View className='report-mini-icon'>
                <Icon name='chart' color='#2563eb' size={32} />
              </View>
              <Text className='home-report-strip__confidence'>{display.match.confidence}</Text>
              <View className='home-report-strip__divider' />
              <Text className='home-report-strip__text'>{display.match.insight}</Text>
            </View>
            <View className='report-link report-link--plain'>
              <Text>查看 AI 赛前报告</Text>
              <Icon name='chevron' color='#2563eb' size={30} />
            </View>
          </View>
        </View>
      ) : (
        <View className='empty-state'>
          <Text>{loadState === 'loading' ? '正在加载真实首页数据' : '真实首页数据不可用'}</Text>
        </View>
      )}

      <Section title='即将开始' action='全部赛程' onAction={() => goTo(routes.matches)}>
        {display?.upcoming.length ? display.upcoming.map(item => {
          const kickoff = splitKickoff(item.time)
          return (
            <View className='match-row match-row--schedule' key={item.id} onClick={() => goTo(`${routes.matchDetail}?matchId=${item.id}`)}>
              <View className='match-row__time'>
                <Text>{kickoff.clock}</Text>
                {kickoff.date ? <Text>{kickoff.date}</Text> : null}
              </View>
              <View className='match-row__fixture'>
                <View className='match-row__team'>
                  <Flag
                    team={item.home}
                    teamId={item.homeTeam?.teamId}
                    teamCode={item.homeTeam?.teamCode}
                    teamEn={item.homeTeam?.nameEn}
                    size='sm'
                  />
                  <Text>{item.home}</Text>
                </View>
                <Text className='match-row__vs'>VS</Text>
                <View className='match-row__team match-row__team--away'>
                  <Flag
                    team={item.away}
                    teamId={item.awayTeam?.teamId}
                    teamCode={item.awayTeam?.teamCode}
                    teamEn={item.awayTeam?.nameEn}
                    size='sm'
                  />
                  <Text>{item.away}</Text>
                </View>
              </View>
              <View className='match-row__trend'>
                <Text>{item.tendency}</Text>
                <Icon name='chevron' color='#94a3b8' size={26} />
              </View>
            </View>
          )
        }) : <View className='empty-state'><Text>暂无真实赛程数据</Text></View>}
      </Section>

      <Section title='冠军概率' action='查看完整榜单' onAction={() => goTo(routes.predictions)}>
        {display?.champions.length ? display.champions.map((team, index) => (
          <View
            className='champion-row'
            key={team.teamId || team.name}
            onClick={() => {
              if (team.teamId) {
                goTo(`${routes.teamDetail}?teamId=${team.teamId}&source=home&rankingType=champion`)
              }
            }}
          >
            <View className={`rank-medal rank-medal--${index + 1}`}>
              <Text>{index + 1}</Text>
            </View>
            <Flag team={team.name} teamId={team.teamId} teamCode={team.teamCode} teamEn={team.nameEn} size='sm' />
            <View className='champion-row__main'>
              <Text className='champion-row__name'>{team.name}</Text>
            </View>
            <View className='champion-row__bar'>
              <ProgressRow label='' value={team.probability} />
            </View>
            <Text className='champion-row__value'>{team.probability}%</Text>
            <Text className={team.delta !== undefined && team.delta < 0 ? 'delta delta--down' : 'delta delta--up'}>
              {team.delta !== undefined ? `${team.delta >= 0 ? '▲' : '▼'} ${Math.abs(team.delta)}%` : ''}
            </Text>
          </View>
        )) : <View className='empty-state'><Text>暂无真实冠军概率数据</Text></View>}
        <Text className='section-footnote'>来自后端真实预测快照</Text>
      </Section>

      {loadState === 'error' ? <Text className='data-note'>真实接口连接失败，未显示虚拟数据。</Text> : null}
      <BottomNav active='matches' />
    </View>
  )
}
