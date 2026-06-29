export default defineAppConfig({
  darkmode: true,
  themeLocation: 'theme.json',
  pages: [
    'pages/matches/index',
    'pages/match-detail/index',
    'pages/groups/index',
    'pages/predictions/index',
    'pages/team-detail/index'
  ],
  window: {
    backgroundTextStyle: '@backgroundTextStyle',
    backgroundColor: '@backgroundColor',
    navigationBarBackgroundColor: '@navigationBarBackgroundColor',
    navigationBarTitleText: '小木绿茵手记',
    navigationBarTextStyle: '@navigationBarTextStyle'
  },
  lazyCodeLoading: 'requiredComponents'
})
