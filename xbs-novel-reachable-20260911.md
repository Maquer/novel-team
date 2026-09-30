# 香色闺阁 小说书源可达性实测报告

> 实测时间 2026-09-11 | 探测环境 iSH(与手机同一网络出口) | 关键词「我」

## 一、总览

| 层级 | 判定标准 | 数量 |
|------|---------|------|
| 小说类启用源 | 分类为 text | **2392** |
| L0 域名可达 | 首页 HTTP 2xx/3xx | **551** 个域名 |
| 🔵 L1 确认可用 | 真实搜索 + 选择器命中≥1 条 | **62** |
| 🟠 L2 选择器失效 | 搜索有返回但 XPath 0 命中（站活、规则过期） | **90** |
| ⚪ L2b 未判定 | 站点在线，但搜索请求依赖 App 内 JS 无法离线构造 | **383** |
| ❌ L3 搜索失败 | 搜索接口 4xx/5xx/超时 | **213** |

> L2 多的原因：书源的 XPath 选择器随目标站改版失效，站点本身仍在。

## 二、失效原因分布（1707 个小说域名）

| 结果 | 域名数 | 含义 |
|------|-------:|------|
| ConnectionError | 685 | DNS失败/连接被拒（站已死） |
| 200 | 548 | 正常 |
| timeout | 330 | 连接超时（被墙/CDN不通/站慢） |
| 403 | 72 | 反爬拦截(Cloudflare等) |
| 404 | 24 | 首页路径已变 |
| 521 | 13 | CDN 回源挂 |
| SSLError | 9 | 证书异常 |
| 503 | 6 | 服务不可用 |
| 530 | 5 | DNS/CDN 配置错 |
| 502 | 4 | 网关错误 |

## 三、🔵 L1 确认可用（搜索实测有结果）

| 书源 | 域名 | 命中条目 | 搜索地址 |
|------|------|--------:|---------|
| cs-万相书城 | www.wxscs.com | 1488 | `https://www.wxscs.com/plus/search.php?q=我` |
| 🌼万相书城 | www.wxscs.com | 1488 | `https://www.wxscs.com/plus/search.php?q=我` |
| 万相书城 | www.wxscs.com | 1488 | `https://www.wxscs.com/plus/search.php?q=我` |
| FZ-爱书包 | www.ishubao.org | 101 | `https://www.ishubao.org/modules/article/search.php?s=1283996` |
| ♡⃝.笔趣阁小说 | www.bi-quge.com | 100 | `http://www.bi-quge.com/search/?searchkey=我` |
| 疯读小说 | fiction.fengduxiaoshuo.com | 100 | `https://fiction.fengduxiaoshuo.com/doReader/search_book?_tok` |
| 🌼绾书文学 | api.wanshu.com | 100 | `https://api.wanshu.com/novel/search?pageSize=100&kw=我` |
| 七彩小说网 | www.qicaizuowen.com | 100 | `https://www.qicaizuowen.com/search/?searchkey=我` |
| 小说77 | www.yeduzhe.com | 100 | `https://www.yeduzhe.com/book/Search.aspx?key=我&p=1` |
| ♡⃝.4小说 | m.4xiaoshuo.info | 50 | `http://m.4xiaoshuo.info/search.php?searchkey=我` |
| ♡⃝.华东看书 | www.dandanwx.com | 50 | `http://www.dandanwx.com/search.html?keyWord=我` |
| 笔趣阁5200 | www.b5200.net | 50 | `http://www.b5200.net/modules/article/search.php?searchkey=我` |
| 看欧洲小说 | kanouzhou.com | 30 | `https://kanouzhou.com/search.html?keyword=我` |
| 松鹤阅读 | bookshelf.html5.qq.com | 21 | `https://so.html5.qq.com/ajax/real/search_result?noTab=1&tabI` |
| 若初文学网 | www.ruochu.com | 20 | `https://search.ruochu.com/m/search?queryString=我&highlight=f` |
| 千金小说网 | www.qianjinge.com | 20 | `https://www.qianjinge.com/Search/我` |
| ⛄️爱下电子书2 | ixdzs8.com | 20 | `https://ixdzs8.com/bsearch?q=我&page=1` |
| 🪵千金小说网 | www.qianjinge.com | 20 | `https://www.qianjinge.com/Search/我` |
| y-潇湘书院 | www.xxsy.net | 20 | `https://www.xxsy.net/search/我` |
| 得间api | wechat.idejian.com | 20 | `https://wechat.idejian.com/api/wechat/search/do?keyword=我&pa` |
| 🌺若初文学网🍪©️ | www.ruochu.com | 20 | `https://search.ruochu.com/m/search?queryString=我&highlight=f` |
| 唯心阅读 | weread.qq.com | 20 | `https://weread.qq.com/web/search/global?count=20&keyword=我&m` |
| 天天看小说 | cn.ttkan.co | 17 | `https://cn.ttkan.co/novel/search?q=我` |
| 天天看小说（yiyanquan） | cn.ttkan.co | 17 | `https://cn.ttkan.co/novel/search?q=我` |
| 猫眼看书 | api.myweipin.com | 15 | `http://api.myweipin.com/search?keyword=我&page=1` |
| 〽️秀亭看书 | www.xiuting.cc | 10 | `https://cn.bing.com/search?q=site:www.xiuting.cc+我` |
| 书耽小说 | www.shubl.com | 10 | `https://www.shubl.com/index/get_search_book_list/我/1` |
| 🌺无限中抓🔭 | www.chinadra.com | 10 | `https://www.chinadra.com/guangboju/guangBoJuList.jsp?srchtxt` |
| 🐲长佩文学🔮🍪©️ | webapi.gongzicp.com | 10 | `https://webapi.gongzicp.com/search/novels?k=我` |
| 🌺书耽🍪©️ | www.shubl.com | 10 | `https://www.shubl.com/index/get_search_book_list/我/1` |
| 长佩文学99 | www.gongzicp.com | 10 | `https://webapi.gongzicp.com/search/novels?k=我&page=1` |
| 长佩文学 | www.gongzicp.com | 10 | `https://webapi.gongzicp.com/search/novels?k=我&page=1` |
| 推书君⛄ | pre-api.tuishujun.com | 10 | `https://pre-api.tuishujun.com/api/searchBook?search_value=我&` |
| 无限中抓 | www.chinadra.com | 10 | `https://www.chinadra.com/guangboju/guangBoJuList.jsp?srchtxt` |
| ou中文网 | www.ouoou.com | 10 | `http://zhannei.baidu.com/cse/site?q=我&s=&cc=ouoou.com` |
| 书耽 | www.shubl.com | 10 | `https://www.shubl.com/index/get_search_book_list/我/1` |
| 小说阅读网无分类 | www.readnovel.com | 9 | `https://www.readnovel.com/so/我` |
| FZ-燃文吧 | www.ranwen8.com | 2 | `https://www.ranwen8.com/modules/article/search.php?searchkey` |
| 3优小说 | www.3uxiaoshuo.com | 0 | `https://www.3uxiaoshuo.com/tag/?key=我` |
| 🌼快读小说网 | www.kuaidu9.com | 0 | `https://www.kuaidu9.com/s?q=我` |
| FZ-笔趣阁bqbi | www.bqbi.cc | 0 | `https://www.bqbi.cc/s?q=我` |
| FZ-BBTXT8 | www.bqbi.cc | 0 | `https://www.bqbi.cc/s?q=我` |
| 🌼海阅小说网 | www.haiyue8.com | 0 | `https://www.haiyue8.com/s?q=我` |
| 🌼笔趣阁688 | www.xiaoshuo688.com | 0 | `https://www.xiaoshuo688.com/search/result.html?searchkey=我` |
| 鲲弩小说 | www.kunnu.com | 0 | `https://www.kunnu.com/page/1/?s=我` |
| 三优小说网⛄️ | www.3uxiaoshuo.com | 0 | `https://www.3uxiaoshuo.com/tag/?key=我` |
| 🎈偶遇吧小说 | www.oue8.com | 0 | `https://www.oue8.com/modules/article/search.php?searchkey=我&` |
| 快读小说网 | m.kuaidu9.com | 0 | `https://m.kuaidu9.com/s?q=我` |
| 🌺镇魂小说📊 | www.zhenhunxiaoshuo.com | 0 | `https://m.baidu.com/s?pn=1&word=我%20site:zhenhunxiaoshuo.com` |
| 米读小说 | www.mdxs123.com | 0 | `https://www.mdxs123.com/s?q=我` |
| 御宅屋life | yuzhaiwu.life | 0 | `https://yuzhaiwu.life/modules/article/search.php?searchkey=我` |
| 镇魂小说 | www.zhenhunxiaoshuo.com | 0 | `https://m.baidu.com/s?pn=1&word=我%20site:zhenhunxiaoshuo.com` |
| FZ-米读小说 | www.mdxs123.com | 0 | `https://www.mdxs123.com/s?q=我` |
| FZ-妙笔读 | www.mbidu.com | 0 | `http://www.mbidu.com/search/result.html?searchkey=我` |
| 👾轻之文库 | www.linovel.net | 0 | `https://www.linovel.net/search?kw=我` |
| 八戒中文网biquka.com | www.biquka.com | 0 | `http://m.biquka.com/search.php?q=我` |
| 轻之文库 | www.linovel.net | 0 | `https://www.linovel.net/search?kw=我` |
| 乐文小说网xlwxsw | www.xlwxsw.com | 0 | `https://www.xlwxsw.com/s123.php?q=我` |
| 八戒书屋 | www.biquka.com | 0 | `http://www.biquka.com/search.php?q=我` |
| 👾八戒中文网 | www.biquka.com | 0 | `http://www.biquka.com/search.php?q=我` |
| 八戒中文网 | www.biquka.com | 0 | `http://www.biquka.com/search.php?q=我` |
| FZ-乐文小说网1 | www.xlwxsw.com | 0 | `https://www.xlwxsw.com/s123.php?q=我` |

（完整 62 个见 [可达小说书源.json](minis://attachments/uploads/%E5%8F%AF%E8%BE%BE%E5%B0%8F%E8%AF%B4%E4%B9%A6%E6%BA%90.json）

## 四、按站点聚合的可用域名 Top 30

| 域名 | 可用书源数 |
|------|----------:|
| www.biquka.com | 4 |
| www.wxscs.com | 3 |
| www.shubl.com | 3 |
| www.ruochu.com | 2 |
| www.qianjinge.com | 2 |
| cn.ttkan.co | 2 |
| www.chinadra.com | 2 |
| www.gongzicp.com | 2 |
| www.3uxiaoshuo.com | 2 |
| www.bqbi.cc | 2 |
| www.zhenhunxiaoshuo.com | 2 |
| www.mdxs123.com | 2 |
| www.linovel.net | 2 |
| www.xlwxsw.com | 2 |
| www.ishubao.org | 1 |
| www.bi-quge.com | 1 |
| fiction.fengduxiaoshuo.com | 1 |
| api.wanshu.com | 1 |
| www.qicaizuowen.com | 1 |
| www.yeduzhe.com | 1 |
| m.4xiaoshuo.info | 1 |
| www.dandanwx.com | 1 |
| www.b5200.net | 1 |
| kanouzhou.com | 1 |
| bookshelf.html5.qq.com | 1 |
| ixdzs8.com | 1 |
| www.xxsy.net | 1 |
| wechat.idejian.com | 1 |
| weread.qq.com | 1 |
| api.myweipin.com | 1 |

## 五、🟠 L2 选择器失效（站点在线，XPath 0 命中，需修规则）

| 书源 | 域名 | HTTP |
|------|------|-----:|
| 🌼冷门小说 | www.lengleng.cc | 200 |
| ∰总监小说 | www.lexuntimes.com | 200 |
| 言情小说阁 | www.xianqihaotianmi.org | 200 |
| ♡⃝.总监小说 | www.lexuntimes.com | 200 |
| 〽️橘色书院 | www.juseshuyuan.com | 200 |
| 书海阁 | m.shuhaige.net | 200 |
| x-完本神站 | www.xiaoshuowanben.com | 200 |
| 格格党51 | m.51ggd.com | 200 |
| 格格党51手机端 | m.51ggd.com | 200 |
| FZ-说说520 | www.shuquta.com | 200 |
| 📖衍墨轩小说 | m.ymxw.net | 200 |
| 🌼酷匠小说 | m.kujiang.com | 200 |
| 雅谷中文网 | eyagu.com | 200 |
| soso笔趣阁 | www.mdbook.net | 200 |
| E品中文 | www.epzw.com | 200 |
| 宙斯小说网 | www.zhsxs.com | 200 |
| 三七中文 | www.777zw.cc | 200 |
| 起点中文网 | www.qidian.com | 202 |
| c-筆趣閣7 | www.biquge7.top | 200 |
| 🌼独步小说网 | dubuxiaoshuo.com | 200 |
| 🎈52格格党 | www.ggdown.org | 200 |
| 🌺百合会小说📊🍪©️ | www.yamibo.com | 200 |
| 秦墟小说 | www.qinxu.org | 200 |
| 🌺booksvooks🌐 | booksvooks.com | 200 |
| 🌺维基阅读 | www.wikiyuedu.com | 200 |
| 笔趣阁bbtxt8 | www.bbtxt8.com | 200 |
| 🦌出品-得间小说 | m.idejian.com | 202 |
| 腐宅屋 | m.fuzhaiwu.net | 200 |
| 御书屋3322 | m.3322t.com | 200 |
| 起点中文(修改自用版1.1) | www.qidian.com | 202 |
| 青空朗読⛄ | www.aozoraroudoku.jp | 200 |
| 起点中文(修改自用版) | www.qidian.com | 202 |
| 漫城小说 | book.acgmh.net | 200 |
| 米读小说123 | www.mdxs123.com | 200 |
| 翻书阁网 | www.fansg.com | 200 |
| 翻书阁(精品) | www.fansg.com | 200 |
| 燃文小说①⛄(搜索间隔30秒) | www.ranwen8.com | 200 |
| 第一版主01 | www.bz01.org | 200 |
| 手打吧小说网 | www.shouda88.com | 200 |
| 思路客客 | www.silukew.com | 200 |

## 五b、⚪ L2b 未判定（站点在线，共 383 个）

这些源的搜索请求写在 `requestInfo` 的 `@js` 里，离线无法还原签名/参数，需在 App 内点一次才知道。

| 书源 | 域名 |
|------|------|
| 多多书院_rm | m.txtduo.org |
| 群小说网1 | www.qunxs.com |
| 〽️28读书 | www.28dushu.com |
| ♡⃝.九九小说 | www.txt9999.org |
| 秋风书屋 | www.qiufengshuwu.com |
| 夜书吧 | www.lisewu.com |
| po18.cloud | m.po18vip.cloud |
| 新御宅屋 | m.xyuzhaiwu.club |
| b5200 | www.abcbiquge.com |
| po18book | m.po18book.com |
| 肉色屋 | m.rousewu.cc |
| 海棠书屋 | www.haitang18.com |
| 飞卢小说网 | wap.faloo.com |
| 🌼情豆书坊 | www.qdsf.net |
| ♡⃝.鲤鱼乡 | www.liyuxiangku.com |
| 📖52书库 | www.52shuwu.net |
| ♡⃝.海棠搜书 | www.haitangss.cc |
| ♡⃝.海棠搜书h | www.hydkg.com |
| 雅文言情 | www.yawen.cc |
| ♡⃝.笔趣阁18 | m.bqg18.cc |
| ♡⃝.书汇小说 | m.shuhui8.cc |
| ♡⃝.笔趣阁mfbqg | m.mfbqg.com |
| ♡⃝.笔趣阁bqgsb | m.bqgsb.cc |
| 中文看 | wap.zwkan.com |
| 📖群小说网 | www.qunxs.com |
| po18wx | m.po18wx.com |
| 📖po18n | m.po18n.com |
| ∰20小说网 | m.20xs.org |
| ♡⃝.书本网net | www.bookdowns.net |
| ♡⃝.妙笔阁📱 | m.mgfggs.net |
| ♡⃝.2k小说阅读 | www.fpxsx.com |
| 人人小说 | www.irrxs.com |
| ♡⃝.顶点小说unionclinic | www.unionclinic.net |
| 晋江文学 | www.jjwxc.net |
| ♡⃝.德佰小说 | www.c-debai.com |
| ♡⃝.商虎小说 | www.shanghu888.com |
| ∰红豆文学 | www.hdwx.net |
| ♡⃝.大美书网 | www.dameishuwang.net |
| ♡⃝.就爱谈小说📱 | m.zqwqlaw.com |
| ∰言情兔 | m.yanqingtu.com |

## 六、说明与边界

- 探测出口 = 本 iPhone 当前网络，与 App 内实际请求同源，但 App 自带 Cookie/UA/JS 引擎，实际可用数可能高于本表（尤其 403 的 72 个站）。
- 未覆盖：需要登录/VIP 的书源、依赖 App 内 JS 沙箱动态签名的源（`parserID: JS` 288 个）。
- L1 判据是「搜『我』有返回条目」，不代表所有书名都能搜到；L2 需人工在 App 里点一次确认。
## 七、全链路实测（62 个可搜源 → 能否真把书读出来）

> 搜索取第一条结果 → 详情页 → 章节目录 → 正文，逐跳真实请求

| 结果 | 数量 | 说明 |
|------|-----:|------|
| ✅ 全链路可读（搜索+目录+正文） | 5 | |
| 🟢 目录通、正文未取到 | 7 | |
| 🟡 详情页通、目录规则失效 | 7 | |
| 🔷 API 源（另测，见下） | 12 | |
| ⚪ 详情链接依赖 App 内 @js 解析 或 站已改结构 | 25 | |
| ⚠️ 复测超时（网络抖动，未判定） | 3 | |
| ⚠️ 复测连不上（未判定） | 2 | |
| ⚠️ 复测连接超时（未判定） | 1 | |

### API 源目录链（12 个）

| 书源 | 结果 | 目录数 | 备注 |
|------|------|------:|------|
| 长佩文学99 | API-empty | 2 | 正文需自备Cookie |
| 疯读小说 | API-OK | 237 |  |
| 🐲长佩文学🔮🍪©️ | API-empty | 2 | 正文需自备Cookie |
| 长佩文学 | API-empty | 0 |  |
| 猫眼看书 | err:MissingSchema | 0 |  |
| 推书君⛄ | chapterlist-needs-js | 0 |  |
| 得间api | chapterlist-needs-js | 0 |  |
| 松鹤阅读 | chapterlist-needs-js | 0 |  |
| 🌼绾书文学 | chapterlist-needs-js | 0 |  |
| 唯心阅读 | chapterlist-needs-js | 0 |  |
| 🌺若初文学网🍪©️ | err:JSONDecodeError | 0 |  |
| 若初文学网 | err:JSONDecodeError | 0 |  |

### ✅ 最终确认「能读完」的 6 个源

| 书源 | 章节数 | 正文字数 |
|------|------:|--------:|
| 小说阅读网无分类 | 1071 | 9917 |
| 小说77 | 2433 | 1089 |
| 看欧洲小说 | 432 | 2470 |
| ♡⃝.笔趣阁小说 | 29 | 3207 |
| y-潇湘书院 | 9 | 6782 |
| 疯读小说（API） | 237 | 正文走 App 内链路 |

> 62 → 6 的落差主要来自：详情/目录链接的取值写在 `@js` 里，我的离线探测器无法执行 App 的 JS 沙箱；这些源在 App 内大概率正常。因此 6 是**离线可证下限**，不是实际上限。
