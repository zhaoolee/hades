import os
import pandas as pd
import re


fileNameMedia = {
    "Achilles": {"zh_cn_desc": "阿喀琉斯(他生前曾是位伟大的英雄，如今成了神殿的警卫长)", "images": ["c5b7b76f2ea376432dc87531f64aa29f.jpg"]},
    "Alecto": {"zh_cn_desc": "阿勒克图(复仇女神墨纪拉的姐姐)", "images": ["Wallpaper_Alecto.png"]},
    "Aphrodite": {"zh_cn_desc": "阿弗洛狄忒(司爱女神)", "images": ["OlympianMontage_Aphrodite.png", "021bec94a44c2f6bb237b91659641947.png"]},
    "Ares": {"zh_cn_desc": "阿瑞斯(战神)", "images": ["OlympianMontage_Ares.png"]},
    "Artemis": {"zh_cn_desc": "阿尔忒弥斯(狩猎女神)", "images": ["ae6f3c551a1391ae7595290f2270c02a.png"]},
    "Athena": {"zh_cn_desc": "雅典娜(智慧女神)", "images": ["Olympians_Athena_01.jpg"]},
    "Chaos": {"zh_cn_desc": "卡俄斯(万物的创造者)", "images": ["Wallpaper_Chaos.jpg"]},
    "Demeter": {"zh_cn_desc": "得墨忒尔(四季女神)", "images": ["Hades_Wallpaper_LongWinter_01.jpg"]},
    "Dionysus": {"zh_cn_desc": "迪奥尼索司(酒神)", "images": ["Wallpaper_Dionysus01.jpg"]},
    "Dusa": {"zh_cn_desc": "杜莎(身负重任的蛇发女妖)", "images": ["b7ab4a3fe3f537c38d49dbb6a3a7e86d.jpg"]},
    "Eurydice": {"zh_cn_desc": "欧律狄克(无忧无虑的缪斯女神)", "images": ["f4cab973f15debf29117853a4fbd253f.jpg"]},
    "ExtraLines": {"zh_cn_desc": "一些零散的补充", "images": ["Blood_Post_01.png"]},
    "Hades": {"zh_cn_desc": "哈迪斯(死者之主)", "images": ["Hades_Post_01.jpg"]},
    "HadesField": {"zh_cn_desc": "哈迪斯的场景", "images": ["5522695dffb86bb104a7998a81494436.jpg", "3c2aca43eb1bced4e5755f14ed136e47.png"]},
    "Hypnos": {"zh_cn_desc": "修普诺斯(睡神)", "images": ["0f9b8f9c6305ad68e31ee481a35d60f4.jpg"]},
    "Intercom": {"zh_cn_desc": "BOSS战斗相关", "images": ["3bdfbff631cfe8ef37f6c5333d758e99.jpg"]},
    "MegaeraField": {"zh_cn_desc": "墨纪拉的场景", "images": ["da77f9e82e6efba1c280a10bae79249b.jpg","33c323fc589cdcddd553e5323571f8f7.jpg","b4e8ac79b52a2364840d7c9896f99300.png"]},
    "MegaeraHome": {"zh_cn_desc": "墨纪拉在家", "images": ["eb3d2a4412bf7cec3eb5978be342fc54.png"]},
    "Minotaur": {"zh_cn_desc": "阿斯忒里俄斯(米诺斯之牛)", "images": ["88065f4356790f4c29e08980b21fb506.jpg"]},
    "Nyx": {"zh_cn_desc": "倪克斯(黑夜之神)", "images": ["night_Post_01.jpg"]},
    "Orpheus": {"zh_cn_desc": "俄耳甫斯(宫廷乐师)", "images": ["293fb146a02d9d767060282bed3affb1.jpg"]},
    "Patroclus": {"zh_cn_desc": "普特洛克勒斯(陨落的勇士)", "images": ["7f82cccde6c473e5f816ec7a8693df1c.png"]},
    "Persephone": {"zh_cn_desc": "珀尔塞福涅(常青女神,冥界皇后)", "images": ["018ca4eec863cf4222c8cd9f3a112462.jpg", "Wallpaper_Persephone.png"]},
    "Poseidon": {"zh_cn_desc": "波塞冬(海神)", "images": ["OlympianMontage_Poseidon.png"]},
    "Scratch": {"zh_cn_desc": "离开", "images": ["f068a6af8826dc56c74d2d090dcad5fe.gif"]},
    "Sisyphus": {"zh_cn_desc": "西西弗斯(他欺骗了亡灵，因此他被判处在塔耳塔罗斯从事长期的劳役)", "images": ["Sisyphus.png"]},
    "Skelly": {"zh_cn_desc": "骨头(训练傀儡)", "images": ["8eb62ecc0b4c5895c83bd0eead18de1d.jpg"]},
    "Songs": {"zh_cn_desc": "歌声", "images": ["816041ad4fd535910c2b259ba7b608a2.jpg","05d5f58e485c89055a3f486de237f4f3.jpg"]},
    "Storyteller": {"zh_cn_desc": "画外音", "images": ["emeareqnd70c1.webp","gf0w7bqnd70c1.png", "8magd7qnd70c1.png", "feghf5pnd70c1.png", "ub7995pnd70c1.png", "l7lo4bqnd70c1.png"]},
    "Thanatos": {"zh_cn_desc": "塔纳托斯(死神)", "images": ["Wallpaper_Thanatos.png"]},
    "ThanatosField": {"zh_cn_desc": "", "images": ["ed3fdfbfcb11bb5337bb8a8867546550.jpg"]},
    "Theseus": {"zh_cn_desc": "忒修斯(雅典英雄)", "images": ["7db6c72f31d9e282d708ca4db03097ee.jpg"]},
    "Tisiphone": {"zh_cn_desc": "提西福涅(复仇三女神之一)", "images": ["Wallpaper_Tisiphone.png"]},
    "ZagreusField": {"zh_cn_desc": "扎格列欧斯区域", "images": ["Wallpaper_Zagreus01.jpg", "Wallpaper_Zagreus02.png"]},
    "ZagreusHome": {"zh_cn_desc": "扎格列欧斯的家", "images": ["gzzxlen8p3l81.png"]},
    "ZagreusScratch": {"zh_cn_desc": "扎格列欧斯离开", "images": ["Hades_Wallpaper_LongWinter_02.jpg"]},
    "Zeus": {"zh_cn_desc": "宙斯(奥林匹斯之王)", "images": ["Olympians_Zeus_01.jpg"]},
}


hadAddedCotent = []

def replaceTemplate(template, reInfo, data):

    reResult = re.findall(reInfo, template)
    new_read_me = template.replace(reResult[0], data)
    return new_read_me


def isDuplicates(content):
    result = False
    if content in hadAddedCotent:
        result = True
    else:
        hadAddedCotent.append(content)
    return result


def clearData(sourceData):
    result = str(sourceData)
    result = result.replace("{!Icons.Music}", "")

    result = re.sub(r"\{#[^}]*\}", "", result)
    result = re.sub(r"<([^>]*)>", r"\1", result)
    return result


def createMarkDownInfo(langCsvInfo):
    fileName = langCsvInfo["en"].split("/")[-1].split(".")[0]
    en_df = pd.read_csv(langCsvInfo["en"])
    zh_cn_df = pd.read_csv(langCsvInfo["zh_cn"])
    result_json = {}

    for index, row in en_df.iterrows():
        if pd.isna(row["ID.2"]) == False:
            content = clearData(row["Line"])
            if content != "nan" and isDuplicates(content) == False:
                result_json[fileName + "_" + row["ID.2"]] = {"en_line": content}

    for index, row in zh_cn_df.iterrows():
        if pd.isna(row["ID.2"]) == False:
            content = clearData(row["Line"])
            if content != "nan":
                if fileName + "_" + row["ID.2"] in result_json:
                    result_json[fileName + "_" + row["ID.2"]]["zh_cn_line"] = content

    result_list = []

    for key in result_json:
        result_list.append(result_json[key])

    # create markdown format text
    markdown_text = ""
    for index, value in enumerate(result_list):
        if index == 0:
            markdown_text += (
                f"<h2 id='{fileName}'>{fileName} {fileNameMedia[fileName]["zh_cn_desc"]} </h2>"
            )
            markdown_text += "<table><tr>" + "<td>EN 🍭</td>" + "<td>ZH-CN 🚀</td></tr>"
        if len(value["en_line"]) > 0 and len(value["zh_cn_line"]) > 0:
            markdown_text += (
                f"<tr><td width='400'>{value["en_line"]}</td><td width='400'>{value["zh_cn_line"]}</td></tr>"
            )

    markdown_text = markdown_text + f"</table><br><a href='#{fileName}Index'>Return {fileName} Index / 返回{fileNameMedia[fileName]["zh_cn_desc"]}目录)</a>"
    # print("==markdown_text==", markdown_text)

    return markdown_text


def main():
    # get ./Subtitles/en dir files whole path
    en_dir = os.path.join(os.getcwd(), "Subtitles", "en")
    zh_cn_dir = os.path.join(os.getcwd(), "Subtitles", "zh-CN")
    en_files = os.listdir(en_dir)
    en_files = sorted(en_files)
    print("==>", en_files)

    filePathLangInfo = {}

    for en_file in en_files:
        filePathLangInfo[en_file] = {}
        filePathLangInfo[en_file]["en"] = os.path.join(en_dir, en_file)
        filePathLangInfo[en_file]["zh_cn"] = os.path.join(zh_cn_dir, en_file)

    # get filePathLangInfo keys list

    filePathLangInfoKeys = list(filePathLangInfo.keys())

    finally_markdown_data = ""

    # add Index

    finally_markdown_data = finally_markdown_data + f"<h2 id='hadesIndex'>Index(目录)</h1>"

    for index, fileNameMediaKey in enumerate(fileNameMedia):

        tmp_images = ""

        for imageIndex, imageSrc in enumerate(fileNameMedia[fileNameMediaKey]["images"]):
            tmp_images = tmp_images + f"<img src='./images/{imageSrc}' height='300'>"


        finally_markdown_data = (
            finally_markdown_data
            + f"<br/><a href='#{fileNameMediaKey}' id='{fileNameMediaKey}Index'><div>{str(fileNameMediaKey)}{' '}{str(fileNameMedia[fileNameMediaKey]["zh_cn_desc"])}</div>{tmp_images}</a><hr/>"
        )

    for filePathLangInfoKey in filePathLangInfoKeys:
        fileMarkDown = createMarkDownInfo(filePathLangInfo[filePathLangInfoKey])
        finally_markdown_data = finally_markdown_data + "\n" + fileMarkDown
    
    readme_md = ""
    with open(os.path.join(os.getcwd(), "EditREADME.md"), "r") as load_f:
        readme_md = load_f.read()
    
    mail_re = r"--hadesEnglishStart----hadesEnglishEnd--"

    new_read_me = replaceTemplate(readme_md, mail_re, finally_markdown_data)

    # write markdown data to markdown file README.md
    try:
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(new_read_me)
    except Exception as e:
        print("write markdown data to markdown file README.md error==", e)

    print("write markdown data to markdown file README.md success")


main()
