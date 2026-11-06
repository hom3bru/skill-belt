import yaml


def main():
    with open("release.yml", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    print("building", config["name"], config["version"])


if __name__ == "__main__":
    main()
