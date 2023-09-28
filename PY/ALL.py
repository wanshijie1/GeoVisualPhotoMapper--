from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import os
import pandas as pd
from datetime import datetime
import ast
import folium


# 定义一个函数来解析EXIF数据
def get_exif_data(image_path):
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        if exif_data:
            exif_info = {}
            for tag, value in exif_data.items():
                tag_name = TAGS.get(tag, tag)
                exif_info[tag_name] = value
            return exif_info
        else:
            return None
    except (IOError, OSError) as e:
        print(f"读取 {image_path} 的EXIF数据时出错，已跳过：{e}")
        return None
    except Exception as e:
        print(f"发生了一个错误，已跳过{image_path}：{e}")
        return None


# 定义一个函数来获取GPS信息
def get_gps_info(exif_data):
    if exif_data and 'GPSInfo' in exif_data:
        gps_info = {}
        for tag, value in exif_data['GPSInfo'].items():
            tag_name = GPSTAGS.get(tag, tag)
            gps_info[tag_name] = value
        return gps_info
    else:
        return None


# 定义一个函数来处理文件夹中的所有照片并保存到CSV文件
def process_photos_and_save_to_csv(folder_path):
    photo_data = []
    for root, dirs, files in os.walk(folder_path):
        for file_name in files:
            if file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                file_path = os.path.join(root, file_name)
                exif_data = get_exif_data(file_path)
                gps_info = get_gps_info(exif_data)
                if gps_info:
                    photo_info = {
                        'File': file_path,
                        'DateTimeOriginal': exif_data.get('DateTimeOriginal', 'N/A'),
                        'Make': exif_data.get('Make', 'N/A'),
                        'Model': exif_data.get('Model', 'N/A'),
                        'GPSInfo': str(gps_info)  # Convert GPSInfo to string
                    }
                    photo_data.append(photo_info)

    if photo_data:
        df = pd.DataFrame(photo_data)
        csv_file_path = 'photo_info.csv'
        df.to_csv(csv_file_path, index=False)  # 将数据保存为CSV文件
        print(f"照片信息已保存为{csv_file_path}文件。")
        return csv_file_path
    else:
        print("未找到带有地理位置信息的照片或无法读取EXIF数据。")
        return None


# 定义一个函数来提取GPS坐标并保存到新的CSV文件
def extract_gps_coordinates_and_save_to_csv(input_csv_file, output_csv_file):
    df = pd.read_csv(input_csv_file)
    new_rows = []

    for index, row in df.iterrows():
        gps_info_str = row['GPSInfo']

        if pd.notna(gps_info_str) and gps_info_str.strip():
            try:
                gps_info_dict = ast.literal_eval(gps_info_str)
                latitude = gps_info_dict.get('GPSLatitude')
                longitude = gps_info_dict.get('GPSLongitude')

                if latitude and longitude:
                    lat_deg, lat_min, lat_sec = latitude
                    lon_deg, lon_min, lon_sec = longitude

                    decimal_latitude = lat_deg + lat_min / 60 + lat_sec / 3600
                    decimal_longitude = lon_deg + lon_min / 60 + lon_sec / 3600

                    new_row = {
                        'GPSLatitude': decimal_latitude,
                        'GPSLongitude': decimal_longitude,
                    }

                    for column in df.columns:
                        if column != 'GPSInfo':
                            new_row[column] = row[column]

                    new_rows.append(new_row)
            except (ValueError, SyntaxError):
                print(f"由于GPS信息解析错误，跳过第 {index} 行。")

    new_df = pd.DataFrame(new_rows)
    new_df.to_csv(output_csv_file, index=False)
    print(f"GPS坐标信息已保存为{output_csv_file}文件。")


# 定义一个函数来可视化GPS坐标在地图上，带有连线路径和控制开关
def visualize_gps_coordinates_on_map(input_csv_file, output_html_file):
    df = pd.read_csv(input_csv_file)
    m = folium.Map(location=[0, 0], zoom_start=2)

    # 定义一个 FeatureGroup 用于添加路径
    line_group = folium.FeatureGroup(name="显示路径", show=False)  # 默认不显示路径

    # 初始化前一张照片的坐标
    prev_latitude, prev_longitude = None, None

    for index, row in df.iterrows():
        try:
            latitude = float(row['GPSLatitude'])
            longitude = float(row['GPSLongitude'])

            # 获取照片的时间信息
            date_str = row['DateTimeOriginal']
            if date_str != 'N/A':
                date = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                date_formatted = date.strftime('%Y-%m-%d %H:%M:%S')

                # 如果有前一张照片的坐标，绘制连线
                if prev_latitude is not None and prev_longitude is not None:
                    folium.PolyLine([(prev_latitude, prev_longitude), (latitude, longitude)],
                                    color='blue',
                                    weight=2,
                                    opacity=1,
                                    popup=f"Time: {date_formatted}").add_to(line_group)

                # 更新前一张照片的坐标
                prev_latitude, prev_longitude = latitude, longitude

            popup_html = f"<b>纬度:</b> {latitude}<br><b>经度:</b> {longitude}<br><b>时间:</b> {date_formatted}"
            folium.Marker([latitude, longitude], popup=popup_html).add_to(m)

        except (ValueError, KeyError):
            pass

    m.add_child(line_group)  # 添加路径到地图

    # 添加控制开关
    folium.LayerControl(collapsed=False).add_to(m)

    m.save(output_html_file)
    print(f"地图已保存为{output_html_file}文件。")


if __name__ == "__main__":
    folder_path = "../1"  # 替换成你的照片文件夹路径

    # 第一步：处理照片并保存到CSV文件
    csv_file_path = process_photos_and_save_to_csv(folder_path)

    if csv_file_path:
        # 第二步：提取GPS坐标并保存到新的CSV文件
        output_csv_path = 'photo_info_with_coordinates.csv'
        extract_gps_coordinates_and_save_to_csv(csv_file_path, output_csv_path)

        # 第三步：可视化GPS坐标在地图上并保存为HTML文件
        output_html_path = os.path.join(os.path.abspath(os.path.join(os.getcwd(), os.pardir)), 'map.html')
        visualize_gps_coordinates_on_map(output_csv_path, output_html_path)

        # 删除两个CSV文件 # 可移除此处功能
        os.remove(csv_file_path)
        os.remove(output_csv_path)
