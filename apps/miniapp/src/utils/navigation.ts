import Taro from '@tarojs/taro'

export const routes = {
  matches: '/pages/matches/index',
  matchDetail: '/pages/match-detail/index',
  groups: '/pages/groups/index',
  predictions: '/pages/predictions/index',
  teamDetail: '/pages/team-detail/index'
}

export function goTo(url: string) {
  Taro.navigateTo({ url }).catch(() => {
    Taro.redirectTo({ url })
  })
}

export function switchSection(url: string) {
  Taro.redirectTo({ url })
}

