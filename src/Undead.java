import java.util.Random;

public class Undead extends GameObject{

	Random r = new Random();
	
	int maxHp;
	
	public Undead(){
		dmg = 4;
		hp = 45;
		name = "Undead";	
		maxHp = 45;
	}
		
}
	
