from app.main import main


def test_main_prints_boot_message(capsys) -> None:
    main()

    captured = capsys.readouterr()
    assert captured.out.strip() == "Villager booted"
