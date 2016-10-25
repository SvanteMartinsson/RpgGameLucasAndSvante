import java.util.Random;

public class Undead extends GameObject{

	Random r = new Random();

	public Undead(){
		dmg = 4;
		hp = 45;
		name = "Undead";
		lvl = 2;
	}

}

