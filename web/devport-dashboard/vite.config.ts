import { mergeConfig } from "vite"
import baseConfig from "../vite.config.base"
import { execFile } from "child_process"

function devportAPI() {
  return {
    name: "devport-api",
    configureServer(server: any) {
      server.middlewares.use("/api/services", (_req: any, res: any) => {
        execFile("devport", ["status", "--json"], (err: any, stdout: string) => {
          res.setHeader("Content-Type", "application/json")
          if (err) {
            res.statusCode = 500
            res.end(JSON.stringify({ error: err.message }))
          } else {
            res.end(stdout)
          }
        })
      })
    },
  }
}

export default mergeConfig(baseConfig, {
  plugins: [devportAPI()],
  server: {
    host: "127.0.0.1",
    port: process.env.VITE_PORT ? Number(process.env.VITE_PORT) : undefined,
    allowedHosts: ["devport.yohoward.com"],
  },
})
