import { PropsWithChildren } from 'react'
import { useLaunch } from '@tarojs/taro'
import './app.scss'

function App({ children }: PropsWithChildren) {
  useLaunch(() => {
    console.log('World Cup prediction miniapp launched.')
  })

  return children
}

export default App

